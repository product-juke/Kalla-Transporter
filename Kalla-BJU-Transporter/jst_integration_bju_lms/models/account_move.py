from odoo import fields, models, _
from odoo.addons.jst_integration_bju_lms.controllers import account_move
import json, datetime, http.client
from odoo.exceptions import ValidationError, UserError
import logging
from urllib.parse import quote
import ssl

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'portfolio.view.mixin']

    invoice_policy = fields.Selection(related='partner_id.invoice_policy', store=True)
    oracle_number = fields.Char(copy=False, tracking=True)
    oracle_sync_statusCode = fields.Char('Status Code', copy=False, tracking=True)
    oracle_sync_message = fields.Char('Message', copy=False, tracking=True)
    oracle_sync_full_message = fields.Text('Full Message', copy=False, tracking=True)
    oracle_sync_date = fields.Datetime('Sync Date', copy=False, tracking=True)
    failed_payment_ar_top = fields.Boolean('Failed Payment AR TOP', copy=False, tracking=True)
    failed_payment_ap = fields.Boolean('Failed Payment AP', copy=False, tracking=True)
    last_middleware_sync_status = fields.Char(copy=False, tracking=True)

    def format_error_messages(self, json_data):
        """
        Format pesan error dengan split koma dan join dengan koma
        """
        try:
            # Cek apakah json_data kosong atau None
            if not json_data:
                _logger.info("On Send Invoice -> No error message available")

            # Cek apakah json_data sudah berupa string
            if isinstance(json_data, str):
                # Coba parse JSON
                data = json.loads(json_data)
            elif isinstance(json_data, dict):
                # Jika sudah berupa dictionary, gunakan langsung
                data = json_data
            else:
                # Jika tipe data tidak dikenali, konversi ke string
                return str(json_data)

            # Ambil array message
            messages = data.get('message', [])

            # Split berdasarkan koma jika ada, lalu join dengan koma
            if isinstance(messages, list):
                # Join semua pesan dengan koma
                formatted = ', '.join(messages)
            else:
                # Jika message bukan list, kembalikan apa adanya
                formatted = str(messages)

            return formatted

        except json.JSONDecodeError as e:
            # Jika gagal parse JSON, kembalikan pesan error atau data asli
            _logger.info(f"On Send Invoice -> Invalid JSON format: {str(json_data)}")
            return '-'

        except Exception as e:
            # Tangani error lainnya
            _logger.info(f"On Send Invoice -> Error processing data: {str(e)} - Data: {str(json_data)}")
            return '-'

    def send_invoice(self):
        # Validasi field yang wajib diisi
        missing_fields = []

        if self.state != 'posted':
            raise ValidationError(_(f'Failed to sync {self.name} (id: {self.id}).\n{self.name} (id: {self.id}) must be in the Posted stage'))
        if self.state == 'draft' and self.oracle_sync_statusCode in ('200', '202') and not self.is_failed_sync_to_oracle:
            raise ValidationError(_(f'Failed to sync {self.name} (id: {self.id}).\n{self.name} (id: {self.id}) already synced'))

        # Validasi company fields
        if not self.company_id.businessUnit:
            missing_fields.append('Kolom "Business Unit" pada Menu Company')
        if not self.company_id.transactionSource:
            missing_fields.append('Kolom "Transaction Source" pada Menu Company')
        if not self.company_id.transactionType:
            missing_fields.append('Kolom "Transaction Type" pada Menu Company')
        if not self.company_id.conversionRateType:
            missing_fields.append('Kolom "Conversion Rate Type" pada Menu Company')

        # Validasi partner
        if not self.partner_id.name:
            missing_fields.append('Nama Customer')

        # Validasi oracle AR lines
        oracle_ar_lines = self.env['oracle.ar.line'].search([('company_id', '=', self.env.company.id)])
        for oracle_ar_line in oracle_ar_lines:
            total = 0
            for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ar_line.account_id):
                total += line.credit - line.debit

            # Hanya validasi jika oracle_ar_line ini akan digunakan (total != 0)
            if total != 0:
                if not oracle_ar_line.memoLineName:
                    missing_fields.append(
                        f'Kolom "Memo Line Name" pada Menu Company (Account: {oracle_ar_line.account_id.name})')
                if not oracle_ar_line.description:
                    missing_fields.append(
                        f'Kolom "Description" pada Menu Company (Account: {oracle_ar_line.account_id.name})')
                # if not oracle_ar_line.taxClassificationCode:
                #     missing_fields.append(
                #         f'Kolom "Tax Classification Code" pada Menu Company (Account: {oracle_ar_line.account_id.name})')

        # Raise UserError jika ada field yang kosong
        if missing_fields:
            error_message = "\nMohon lengkapi kolom berikut sebelum mengirim Invoice ke Oracle:\n"
            for field in missing_fields:
                error_message += f"• {field}\n"
            raise UserError(error_message)

        invoiceLines = []
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        clientId = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientId')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        route = '/oracle-integration/api/invoice-ar'
        count = 1
        oracle_ar_lines = self.env['oracle.ar.line'].search([('company_id', '=', self.env.company.id)])


        portfolio = 'transporter'
        is_vli = self.env.company.portfolio_id.name.upper() == 'VLI'

        program_category_id = None
        vli_transaction_type = None
        for line in self.invoice_line_ids:
            if line.product_id.vehicle_category_id and line.product_id.vehicle_category_id.program_category_id:
                program_category_id = line.product_id.vehicle_category_id.program_category_id
                break

        if is_vli:
            oracle_ar_lines = oracle_ar_lines.filtered(lambda x: program_category_id == x.program_category_id)
            vli_transaction_type = self.env['oracle.program.transaction.type'].search([
                ('program_category_id', '=', program_category_id.id)
            ], limit=1)
            if not vli_transaction_type:
                raise UserError(_(f"Belum ada Transaction Type yang dikonfigurasi pada program {program_category_id.name}."))


        invoiceHeader = {
            "trxNumber": self.name,
            "trxDate": self.invoice_date.strftime('%Y-%m-%d'),
            "glDate": self.invoice_date.strftime('%Y-%m-%d'),
            "businessUnit": self.company_id.businessUnit,
            "transactionSource": self.company_id.transactionSource,
            "transactionType": self.company_id.transactionType if not is_vli else vli_transaction_type.transaction_type,
            "billToCustomerName": self.partner_id.name,
            "billToAccountNumber": self.partner_id.vat,
            "paymentTermsName": self.invoice_payment_term_id.name if self.invoice_payment_term_id.name else "IMMEDIATE",
            "invoiceCurrencyCode": self.currency_id.name,
            "conversionRateType": self.company_id.conversionRateType,
            "countLines": str(len(invoiceLines)) if is_vli else str(len(self.invoice_line_ids)),
            "createdBy": self.create_uid.name,
        }

        if self.is_lms(self.env.company.portfolio_id.name):
            _logger.info(f"Prepare Payload for ORACLE Integration Transporter")
            for oracle_ar_line in oracle_ar_lines:
                total = 0
                tax = False
                taxes = []
                curr_acc_id = None
                if is_vli:
                    _logger.info(f"Prepare Payload for ORACLE Integration VLI => {program_category_id}")
                    for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ar_line.account_id):
                        total += line.credit - line.debit
                        curr_acc_id = line.account_id
                        if line.tax_ids:
                            taxes = line.tax_ids
                            tax = True
                else:
                    for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ar_line.account_id):
                        total += line.credit - line.debit
                        if line.tax_ids:
                            taxes = line.tax_ids
                            tax = True

                if total != 0 and not is_vli:
                    if tax:
                        inv_line = {
                            "trxNumber": self.name,
                            "lineNumber": str(count),
                            "memoLineName": oracle_ar_line.memoLineName,
                            "description": oracle_ar_line.description,
                            "quantity": "1",
                            "unitSellingPrice": str(total),
                            # "taxClassificationCode": oracle_ar_line.taxClassificationCode or None
                        }

                        for tax_id in taxes:
                            if not tax_id.oracle_tax_name:
                                raise ValidationError(_(f"Oracle Tax Name untuk tax \"{tax_id.name}\" harus diisi!"))
                            else:
                                if tax_id.group == 'ppn':
                                    inv_line['taxClassificationCode'] = tax_id.oracle_tax_name
                                if tax_id.group == 'pph':
                                    inv_line['Withholding'] = tax_id.oracle_tax_name
                                    invoiceHeader['InvoiceAmount'] = "{:.2f}".format(sum(self.line_ids.mapped('credit')))

                        invoiceLines.append(inv_line)

                    else:
                        invoiceLines.append({
                            "trxNumber": self.name,
                            "lineNumber": str(count),
                            "memoLineName": oracle_ar_line.memoLineName,
                            "description": oracle_ar_line.description,
                            "quantity": "1",
                            "unitSellingPrice": str(total)
                        })
                elif is_vli:
                    if tax:
                        inv_line = {
                            "trxNumber": self.name,
                            "lineNumber": str(count),
                            "memoLineName": oracle_ar_line.memoLineName,
                            "description": oracle_ar_line.description,
                            "quantity": "1",
                            "unitSellingPrice": str(total),
                            # "taxClassificationCode": oracle_ar_line.taxClassificationCode or None
                        }

                        for tax_id in taxes:
                            if not tax_id.oracle_tax_name:
                                raise ValidationError(_(f"Oracle Tax Name untuk tax \"{tax_id.name}\" harus diisi!"))
                            else:
                                if tax_id.group == 'ppn':
                                    inv_line['taxClassificationCode'] = tax_id.oracle_tax_name
                                if tax_id.group == 'pph':
                                    inv_line['Withholding'] = tax_id.oracle_tax_name
                                    invoiceHeader['InvoiceAmount'] = "{:.2f}".format(sum(self.line_ids.mapped('credit')))

                        invoiceLines.append(inv_line)

                    else:
                        invoiceLines.append({
                            "trxNumber": self.name,
                            "lineNumber": str(count),
                            "memoLineName": oracle_ar_line.memoLineName,
                            "description": oracle_ar_line.description,
                            "quantity": "1",
                            "unitSellingPrice": str(total)
                        })
                count += 1
        else:
            portfolio = 'frozen'
            _logger.info(f"Prepare Payload for ORACLE Integration Frozen")
            for oracle_ar_line in oracle_ar_lines:
                total = 0
                tax = False
                for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ar_line.account_id):
                    total += line.credit - line.debit
                    if line.tax_ids:
                        tax = True

                if total != 0:
                    if tax:
                        invoiceLines.append({
                            "trxNumber": str(self.name),
                            "lineNumber": str(count),
                            "memoLineName": str(oracle_ar_line.memoLineName),
                            "description": str(oracle_ar_line.description),
                            "quantity": str(1),
                            "unitSellingPrice": str(total),
                            "taxClassificationCode": str(oracle_ar_line.taxClassificationCode)
                        })
                    else:
                        invoiceLines.append({
                            "trxNumber": str(self.name),
                            "lineNumber": str(count),
                            "memoLineName": str(oracle_ar_line.memoLineName),
                            "description": str(oracle_ar_line.description),
                            "quantity": str(1),
                            "unitSellingPrice": str(total)
                        })
                count += 1

        datas = {
            "invoiceHeader": invoiceHeader,
            "invoiceLines": invoiceLines
        }

        is_resend = self.env.context.get('is_resend')
        if is_resend:
            _logger.info('On Resend Customer to Oracle')
            datas['resend'] = True

        conn = http.client.HTTPSConnection(url, port or None)
        payload = json.dumps(datas)
        headers = {
            'clientId': clientId,
            'Authorization': Authorization,
            'User-Agent': UserAgent,
            'Content-Type': 'application/json'
        }
        conn.request("POST", route, payload, headers)
        res = conn.getresponse()
        res_body = res.read().decode('utf-8')

        _logger.info(f'Status Code: {res.status}')
        _logger.info(f'Response: {res.reason}')
        _logger.info(f"Response Body: {res_body}")
        # _logger.info('Headers:', headers)
        _logger.info(f'Payload => {payload}')

        # Fix for the singleton error - handle multiple sale orders
        sale_orders = self.line_ids.sale_line_ids.order_id
        oracle_number = self.name  # Default to invoice name

        if sale_orders:
            # Check if any of the sale orders has invoice_policy == 'order'
            order_policy_orders = sale_orders.filtered(lambda order: order.invoice_policy == 'order')
            if order_policy_orders:
                # Use the first order's name if there are orders with 'order' policy
                oracle_number = order_policy_orders[0].name

        self.oracle_number = oracle_number
        self.oracle_sync_statusCode = res.status
        self.oracle_sync_message = res.reason
        if res_body:
            self.oracle_sync_full_message = self.format_error_messages(res_body)
        self.oracle_sync_date = fields.Datetime.now()

        if res.status and res.status in (200, 202, '200', '202', 400, '400', 422, '422'):
            self.env['middleware.response.request.log'].create({
                'res_id': self.id,
                'name': self.name,
                'res_model': 'account.move',
                'sync_status_code': int(res.status),
                'sync_message': self.format_error_messages(res_body) if res_body else res.reason,
                'payload_sent': str(payload),
                'portfolio': portfolio,
                'description': 'Send Invoice AR'
            })

    def send_invoice_ap(self):
        invoiceLines = []
        is_lms = self.is_lms(self.env.company.portfolio_id.name)

        if self.state != 'posted':
            raise ValidationError(_(f'Failed to sync {self.name} (id: {self.id}).\n{self.name} (id: {self.id}) must be in the Posted stage'))
        if self.state == 'draft' and self.oracle_sync_statusCode in ('200', '202') and not self.is_failed_sync_to_oracle:
            raise ValidationError(_(f'Failed to sync {self.name} (id: {self.id}).\n{self.name} (id: {self.id}) already synced'))

        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        clientId = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientId')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        route = '/oracle-integration/api/invoice-ap'
        count = 1
        portfolio = 'transporter'

        if is_lms:
            invoiceHeader = {
                "InvoiceNumber": self.name,
                "InvoiceCurrency": self.currency_id.name,
                "PaymentCurrency": self.currency_id.name,
                # "InvoiceAmount": "{:.2f}".format(self.amount_total),
                "InvoiceAmount": int(self.amount_total),
                "InvoiceDate": self.invoice_date.strftime('%Y-%m-%d'),
                "BusinessUnit": self.company_id.businessUnit,
                "Supplier": self.partner_id.name,
                "SupplierSite": self.partner_id.supplier_site,
                # "transactionSource": self.company_id.transactionSource,
                # "transactionType": self.company_id.transactionType,
                "AccountingDate": self.date.strftime('%Y-%m-%d'),
                "Description": self.ref if self.ref else "",
                "InvoiceType": "Standard",
                "PaymentMethodCode": "KALLA_ELECTRONIC",
                "PaymentTerms": self.invoice_payment_term_id.name if self.invoice_payment_term_id.name else "IMMEDIATE",
            }
        else:
            portfolio = 'frozen'
            invoiceHeader = {
                "InvoiceNumber": self.name,
                "InvoiceCurrency": self.currency_id.name,
                "PaymentCurrency": self.currency_id.name,
                "InvoiceAmount": "{:.2f}".format(self.amount_total),
                "InvoiceDate": self.invoice_date.strftime('%Y-%m-%d'),
                "BusinessUnit": self.company_id.businessUnit,
                "Supplier": str(self.partner_id.Supplier),
                "SupplierSite": str(self.partner_id.SupplierSite),
                "transactionSource": self.company_id.transactionSource,
                "transactionType": self.company_id.transactionType,
                "AccountingDate": self.date.strftime('%Y-%m-%d'),
                "Description": self.narration if self.narration else " ",
                "InvoiceType": "Standard",
                "PaymentMethodCode": "KALLA_ELECTRONIC",
                "PaymentTerms": self.invoice_payment_term_id.name if self.invoice_payment_term_id.name else "IMMEDIATE",
            }

        oracle_ap_lines = self.env['oracle.ap.line'].search([('company_id', '=', self.env.company.id)])
        is_vli = self.env.company.portfolio_id.name.upper() == 'VLI'

        program_category_id = None
        vli_transaction_type = None
        for line in self.invoice_line_ids:
            if line.product_id.vehicle_category_id and line.product_id.vehicle_category_id.program_category_id:
                program_category_id = line.product_id.vehicle_category_id.program_category_id
                break

        if not program_category_id:
            for line in self.invoice_line_ids:
                if line.move_id.bop_line_ids:
                    for bop_line in line.move_id.bop_line_ids:
                        if bop_line.fleet_do_id:
                            program_category_id = bop_line.fleet_do_id.category_id.program_category_id

        if is_vli:
            oracle_ap_lines = oracle_ap_lines.filtered(lambda x: program_category_id == x.program_category_id)
            if program_category_id:
                vli_transaction_type = self.env['oracle.program.transaction.type'].search([
                    ('program_category_id', '=', program_category_id.id)
                ], limit=1)
                if not vli_transaction_type:
                    raise UserError(_(f"Belum ada Transaction Type yang dikonfigurasi pada program {program_category_id.name}."))

        if is_lms:
            portfolio = 'transporter'
            _logger.info(f"Oracle AP Lines in LMS: {oracle_ap_lines} -> {len(oracle_ap_lines)}")
            for oracle_ap_line in oracle_ap_lines:
                total = 0
                tax = False
                taxes = []
                lines = {}
                for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ap_line.account_id):
                    total += line.debit - line.credit
                    if line.tax_ids:
                        # if oracle_ap_line.taxClassification:
                        tax = True
                        taxes = line.tax_ids
                        lines[count] = line

                _logger.info(f"Total Debit Credit: {total} -> {total != 0}")
                _logger.info(f"Tax is Exist: {tax}")
                if total != 0:
                    if tax:
                        bill_line = {
                            "LineNumber": count,
                            # "LineAmount": "{:.2f}".format(total),
                            "LineAmount": int(total),
                            "AccountingDate": self.date.strftime('%Y-%m-%d'),
                            "LineType": "Item",
                            "Description": lines[count].name if lines[count] else "",
                            "DistributionSet": oracle_ap_line.DistributionSet,
                        }

                        for tax_id in taxes:
                            if not tax_id.oracle_tax_name:
                                raise ValidationError(_(f"Oracle Tax Name untuk tax \"{tax_id.name}\" harus diisi!"))
                            else:
                                if tax_id.group == 'ppn':
                                    bill_line['TaxClassification'] = tax_id.oracle_tax_name
                                if tax_id.group == 'pph':
                                    bill_line['Withholding'] = tax_id.oracle_tax_name
                                    # invoiceHeader['InvoiceAmount'] = "{:.2f}".format(sum(self.line_ids.mapped('credit')))
                                    invoiceHeader['InvoiceAmount'] = sum(self.line_ids.mapped('credit'))

                        invoiceLines.append(bill_line)
                        count += 1
                    else:
                        invoiceLines.append({
                            "LineNumber": count,
                            # "LineAmount": "{:.2f}".format(total),
                            "LineAmount": int(total),
                            "AccountingDate": self.date.strftime('%Y-%m-%d'),
                            "LineType": "Item",
                            "Description": self.name if self.name else "",
                            "DistributionSet": oracle_ap_line.DistributionSet,
                        })
                        count += 1
        else:
            portfolio = 'frozen'
            _logger.info(f"Oracle AP Lines in Frozen: {oracle_ap_lines} -> {len(oracle_ap_lines)}")
            for oracle_ap_line in oracle_ap_lines:
                total = 0
                tax = False
                for line in self.line_ids.filtered(lambda x: x.account_id == oracle_ap_line.account_id):
                    total += line.debit - line.credit
                    if line.tax_ids:
                        if oracle_ap_line.taxClassification:
                            tax = True

                _logger.info(f"Total Debit Credit: {total} -> {total != 0}")
                _logger.info(f"Tax is Exist: {tax}")
                if total != 0:
                    if tax:
                        _logger.info("TAX")
                        invoiceLines.append({
                            "LineNumber": str(count),
                            "LineAmount": total,
                            "AccountingDate": str(self.date.strftime('%Y-%m-%d')),
                            "LineType": str("Item"),
                            "Description": str(self.narration if self.narration else ""),
                            "DistributionSet": str(oracle_ap_line.DistributionSet),
                            "TaxClassification": str(oracle_ap_line.taxClassification)
                        })
                        count += 1
                    else:
                        _logger.info("NO TAX")
                        invoiceLines.append({
                            "LineNumber": str(count),
                            "LineAmount": total,
                            "AccountingDate": str(self.date.strftime('%Y-%m-%d')),
                            "LineType": str("Item"),
                            "Description": str(self.narration if self.narration else ""),
                            "DistributionSet": str(oracle_ap_line.DistributionSet),
                            # "TaxClassification": ""
                        })

                        count += 1

        datas = {
            "invoiceHeader": invoiceHeader,
            "invoiceLines": invoiceLines
        }

        is_resend = self.env.context.get('is_resend')
        if is_resend:
            _logger.info('On Resend Customer to Oracle')
            datas['resend'] = True

            if self.state in ('posted', 'cancel') and not self.is_failed_sync_to_oracle:
                state_label = "di confirm" if self.state == 'posted' else "di cancel"
                raise ValidationError(_(f"Bill yang sudah {state_label} tidak bisa di re-sync ke Oracle."))

        conn = http.client.HTTPSConnection(url, port or None)
        payload = json.dumps(datas)
        headers = {
            'clientId': clientId,
            'Authorization': Authorization,
            'User-Agent': UserAgent,
            'Content-Type': 'application/json'
        }
        conn.request("POST", route, payload, headers)
        res = conn.getresponse()
        res_body = res.read().decode('utf-8')

        _logger.info(f'Status Code: {res.status}')
        _logger.info(f'Response: {res.reason}')
        _logger.info(f"Response Body: {res_body}")
        # _logger.info('Headers:', headers)
        _logger.info(f'Payload => {payload}')

        self.oracle_number = self.name
        self.oracle_sync_statusCode = res.status
        self.oracle_sync_message = res.reason
        if res_body:
            self.oracle_sync_full_message = self.format_error_messages(res_body)
        self.oracle_sync_date = fields.Datetime.now()

        if res.status and res.status in (200, 202, '200', '202', 400, '400', 422, '422'):
            self.env['middleware.response.request.log'].create({
                'res_id': self.id,
                'name': self.name,
                'res_model': 'account.move',
                'sync_status_code': int(res.status),
                'sync_message': self.format_error_messages(res_body) if res_body else res.reason,
                'payload_sent': str(payload),
                'portfolio': portfolio,
                'description': 'Send Invoice AP'
            })

    def action_post(self):
        if self.move_type == 'in_invoice' and not self.ref:
            raise ValidationError(_("Bill Reference must filled!"))
        res = super(AccountMove, self).action_post()
        if self.state == 'posted':
            self.name = self.name.replace("/", "-")
            sync_ar_to_oracle = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.sync_ar_to_oracle')
            sync_ap_to_oracle = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.sync_ap_to_oracle')
            use_queue_ar = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.use_queue_ar')
            use_queue_ap = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.use_queue_ap')
            if self.move_type == 'out_invoice' and sync_ar_to_oracle:
                if use_queue_ar:
                    self.with_delay().send_invoice()
                else:
                    self.send_invoice()
            elif self.move_type == 'in_invoice' and sync_ap_to_oracle:
                if use_queue_ap:
                    self.with_delay().send_invoice_ap()
                else:
                    self.send_invoice_ap()
        return res

    def action_get_invoice_ar(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        conn = http.client.HTTPSConnection(url, port or None)
        payload = ''
        headers = {
            'Authorization': Authorization,
            'User-Agent': UserAgent
        }
        route = '/oracle-integration/api/invoice-ar'
        # Fix untuk menangani multiple sale orders
        order_ids = self.line_ids.sale_line_ids.mapped('order_id')

        # Cek apakah ada sale order dan semua order memiliki invoice_policy == 'order'
        if order_ids and all(order.invoice_policy == 'order' for order in order_ids):
            oracle_number = self.name.replace('/', '%2f') if '/' in self.name else self.name
        else:
            oracle_number = self.oracle_number.replace('/', '%2f') if '/' in self.oracle_number else self.oracle_number
        _logger.info(f"oracle_number: {oracle_number}")
        conn.request("GET", '%s/%s' % (route, oracle_number), payload, headers)
        res = conn.getresponse()
        data = res.read()
        data = data.decode("utf-8")

        if 'forbidden' in str(data).lower():
            raise ValidationError(_(f"Sistem mengalami kendala saat berkomunikasi dengan Oracle.\nSilakan coba lagi beberapa saat lagi, atau hubungi admin jika masalah terus berlanjut.\n\nPesan dari sistem: {str(data)}"))

        try:
            response = json.loads(data)
            # Ambil message dari response json
            if 'flag' in response:
                if response['flag'] not in ['ADD', 'SENT']:
                    message = f"{response['flag']} ===> {response.get('messages')}"
                else:
                    message = response['flag']
            else:
                message = response.get('message', str(response))  # fallback
        except json.JSONDecodeError:
            # Kalau tidak bisa di-parse JSON, berarti response string biasa
            message = data

        self.env['middleware.response.request.log'].create({
            'res_id': self.id,
            'name': self.name,
            'res_model': 'account.move',
            'sync_status_code': int(res.status),
            'sync_message': message,
            'payload_sent': str(payload),
            'portfolio': str(self.env.company.portfolio_id.name).lower() if str(self.env.company.portfolio_id.name).lower() in ('frozen', 'transporter', 'vli') else None,
            'description': 'Get Invoice AR'
        })
        self.last_middleware_sync_status = message

        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Response',
                'message': message,
                'sticky': False,
                'type': 'warning',
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }
        return action

    def action_get_invoice_ap(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')

        conn = http.client.HTTPSConnection(url, port or None)
        payload = ''
        headers = {
            'User-Agent': UserAgent,
            'Authorization': Authorization
        }
        route = '/oracle-integration/api/invoice-ap'
        conn.request("GET", '%s/%s' % (route, self.oracle_number.replace('/', '%2f') if '/' in self.oracle_number else self.oracle_number), payload, headers)
        res = conn.getresponse()
        data = res.read()
        data = data.decode("utf-8")
        if 'forbidden' in str(data).lower():
            raise ValidationError(_(f"Sistem mengalami kendala saat berkomunikasi dengan Oracle.\nSilakan coba lagi beberapa saat lagi, atau hubungi admin jika masalah terus berlanjut.\n\nPesan dari sistem: {str(data)}"))
        elif 'bad gateway' in str(data).lower():
            action = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Response',
                    'message': 'Bad Gateway. \nToo many requests, please try again in a few moments.',
                    'sticky': False,
                    'type': 'warning',
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    }
                }
            }
            return action

        # Try to parse JSON response
        try:
            response = json.loads(data)
            if 'flag' in response:
                if response['flag'] not in ['ADD', 'SENT']:
                    message = '%s ===> %s' % (response['flag'], response['messages'])
                else:
                    message = response['flag']
            else:
                message = response.get('message', 'No message provided')
        except (json.JSONDecodeError, ValueError) as e:
            # Handle invalid JSON response
            message = f"Invalid response from server: {data[:200]}"  # Log first 200 chars
            _logger.error(f"JSON decode error in action_get_invoice_ap: {str(e)}\nResponse data: {data}")

        self.env['middleware.response.request.log'].create({
            'res_id': self.id,
            'name': self.name,
            'res_model': 'account.move',
            'sync_status_code': int(res.status),
            'sync_message': message,
            'payload_sent': str(payload),
            'portfolio': str(self.env.company.portfolio_id.name).lower() if str(self.env.company.portfolio_id.name).lower() in ('frozen', 'transporter', 'vli') else None,
            'description': 'Get Invoice AP'
        })
        self.last_middleware_sync_status = message

        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Response',
                'message': message,
                'sticky': False,
                'type': 'warning',
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }
        return action

    def register_payment_ar_top(self, receipt):
        journal_id = self.env['account.journal'].search([('bank_account_id.acc_holder_name', '=', receipt['G_2']['BANK_ACCOUNT_NAME'])], limit=1)
        if not journal_id:
            raise ValidationError(_("Bank Account Name : %s does'nt exist!" % receipt['G_2']['BANK_ACCOUNT_NAME']))
        else:
            payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=self.ids).create({
                'journal_id': journal_id.id,
                'company_id': journal_id.company_id.id,
                'amount': "{:.2f}".format(float(receipt['G_2']['AMOUNT_APPLIED'])),
                'payment_date': fields.Date.today(),
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'communication': receipt['TRX_NUMBER']
            })

        payment_diff = self.amount_residual - payment_register.amount
        if payment_diff <= 500:
            payment_register.writeoff_account_id = int(self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_account_id'))
            payment_register.writeoff_label = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_label')
            payment_register.payment_difference_handling = 'reconcile'

        # create payment
        new_payment_id = payment_register.action_create_payments()
        payment_id = self.env['account.payment'].search([('id', '=', new_payment_id['res_id'])])
        payment_id.CASH_RECEIPT_ID = receipt['G_2']['CASH_RECEIPT_ID']
        payment_id.RECEIPT_NUMBER = receipt['G_2']['RECEIPT_NUMBER']
        return payment_id

    def register_payment_ar_top_list(self, receipt, G_2):
        journal_id = self.env['account.journal'].search([('bank_account_id.acc_holder_name', '=', G_2['BANK_ACCOUNT_NAME'])], limit=1)
        if not journal_id:
            raise ValidationError(_("Bank Account Name : %s does'nt exist!" % G_2['BANK_ACCOUNT_NAME']))
        else:
            payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=self.ids).create({
                'journal_id': journal_id.id,
                'company_id': journal_id.company_id.id,
                'amount': "{:.2f}".format(float(G_2['AMOUNT_APPLIED'])),
                'payment_date': fields.Date.today(),
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'communication': receipt['TRX_NUMBER']
            })

        payment_diff = self.amount_residual - payment_register.amount
        if payment_diff <= 500:
            payment_register.writeoff_account_id = int(self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_account_id'))
            payment_register.writeoff_label = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_label')
            payment_register.payment_difference_handling = 'reconcile'

        # create payment
        new_payment_id = payment_register.action_create_payments()
        payment_id = self.env['account.payment'].search([('id', '=', new_payment_id['res_id'])])
        payment_id.CASH_RECEIPT_ID = G_2['CASH_RECEIPT_ID']
        payment_id.RECEIPT_NUMBER = G_2['RECEIPT_NUMBER']
        return payment_id

    def register_payment_ap(self, receipt):
        journal_id = self.env['account.journal'].search([('bank_account_id.acc_holder_name', '=', receipt['BANK_ACCOUNT_NAME'])], limit=1)
        if not journal_id:
            raise ValidationError(_("Bank Account Name : %s does'nt exist!" % receipt['BANK_ACCOUNT_NAME']))
        else:
            payment_register = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=self.ids).create({
                'journal_id': journal_id.id,
                'company_id': journal_id.company_id.id,
                'amount': "{:.2f}".format(float(receipt['AMOUNT_APPLIED'])),
                'payment_date': fields.Date.today(),
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'communication': receipt['TRX_NUMBER']
            })

            payment_diff = self.amount_residual - payment_register.amount
            if payment_diff <= 500:
                payment_register.writeoff_account_id = int(self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_account_id'))
                payment_register.writeoff_label = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.writeoff_label')
                payment_register.payment_difference_handling = 'reconcile'

            # create payment
            new_payment_id = payment_register.action_create_payments()
            payment_id = self.env['account.payment'].search([('id', '=', new_payment_id['res_id'])])
            payment_id.CHECK_ID = receipt['CHECK_ID']
            return payment_id

    def action_get_payment_ar_top(self):
        for rec in self:
            if rec.state == 'posted' and rec.move_type == 'out_invoice':
                # url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
                # port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
                Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
                UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

                # conn = http.client.HTTPSConnection(url, port or None)

                context = ssl._create_unverified_context()
                conn = http.client.HTTPSConnection('api-integration-dev.kallagroup.co.id', 8443, context=context)

                payload = ''
                headers = {
                    'Authorization': Authorization,
                    'User-Agent': UserAgent
                }

                receipt_number = rec.oracle_number
                encoded_receipt_number = quote(str(receipt_number))
                # route = '/oracle-integration/api/receipt'
                route = '/receipt_invoice'
                conn.request("GET", '%s?number=%s' % (route, encoded_receipt_number), payload, headers)
                res = conn.getresponse()
                data = res.read()
                data = data.decode("utf-8")
                response = json.loads(data)
                _logger.info(f"Response Payment AR TOP => {response}")
                if 'data' in response:
                    _logger.info(f"Response Payment AR TOP => {response['data']}")
                    for receipt in response['data']:
                        if 'G_2' not in receipt:
                            rec.failed_payment_ar_top = True
                        else:
                            is_array = isinstance(receipt['G_2'], list)
                            if is_array:
                                for G_2 in receipt['G_2']:
                                    payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['TRX_NUMBER']), ('CASH_RECEIPT_ID', '=', G_2['CASH_RECEIPT_ID'])])
                                    if not payment_id:
                                        if G_2['RECEIPT_STATUS'] in ['APP', 'UNAPP']:
                                            if G_2['DISPLAY'] in ['Y']:
                                                rec.register_payment_ar_top_list(receipt, G_2)
                                    else:
                                        if G_2['RECEIPT_STATUS'] in ['REV', 'STOP'] and int(G_2['AMOUNT_APPLIED']) > 0:
                                            payment_id.action_draft()
                                            payment_id.action_cancel()
                            else:
                                payment_id = self.env['account.payment'].search([('state', 'in', ['posted','cancel']), ('ref', '=', receipt['TRX_NUMBER']), ('CASH_RECEIPT_ID', '=', receipt['G_2']['CASH_RECEIPT_ID'])])
                                if not payment_id:
                                    rec.register_payment_ar_top(receipt)
                else:
                    action = {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Response',
                            'message': response['message'],
                            'sticky': False,
                            'type': 'warning',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                            }
                        }
                    }
                    return action

    def action_get_payment_ap(self):
        for rec in self:
            if rec.state == 'posted' and rec.move_type == 'in_invoice':
                url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
                port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
                Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
                UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')
                company_id = self.env['res.company'].sudo().search([('id', '=', self.env.company.id)])

                if not company_id.org:
                    raise UserError(_("Mohon lengkapi kolom \"Org\" Pada menu Company."))

                conn = http.client.HTTPSConnection(url, port or None)
                payload = ''
                headers = {
                    'Authorization': Authorization,
                    'User-Agent': UserAgent
                }
                route = '/oracle-integration/api/payment'
                conn.request("GET", '%s?org-id=%s&invoice-number=%s' % (route, company_id.org, rec.oracle_number), payload, headers)
                res = conn.getresponse()
                data = res.read()
                data = data.decode("utf-8")
                response = json.loads(data)
                _logger.info(f"Response Payment AP => {response}, {company_id.org}, {rec.oracle_number}")
                if 'data' in response:
                    _logger.info(f"Response Payment AP => {response['data']}")
                    for receipt in [response['data']]:
                        _logger.info(f"Response Payment AP => {receipt}")
                        is_array = isinstance(receipt['G_2'], list)
                        if is_array:
                            for G_2 in receipt['G_2']:
                                payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', G_2['TRX_NUMBER']), ('amount', '=', G_2['AMOUNT_APPLIED']), ('CHECK_ID', '=', G_2['CHECK_ID'])])
                                if payment_id:
                                    if G_2["STATUS_LOOKUP_CODE"] == "VOIDED" and payment_id.state == 'posted':
                                        payment_id.action_draft()
                                        payment_id.action_cancel()
                                if not payment_id:
                                    if G_2["STATUS_LOOKUP_CODE"] == "CLEARED":
                                        rec.register_payment_ap(G_2)
                        else:
                            payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['G_2']['TRX_NUMBER']), ('amount', '=', receipt['G_2']['AMOUNT_APPLIED']), ('CHECK_ID', '=', receipt['G_2']['CHECK_ID'])])
                            if payment_id:
                                if receipt['G_2']["STATUS_LOOKUP_CODE"] == "VOIDED" and payment_id.state == 'posted':
                                    payment_id.action_draft()
                                    payment_id.action_cancel()
                            if not payment_id:
                                if receipt['G_2']["STATUS_LOOKUP_CODE"] == "CLEARED":
                                    rec.register_payment_ap(receipt['G_2'])
                else:
                    if 'success' in response:
                        if response['success'] == False:
                            rec.failed_payment_ap = True
                    action = {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Response',
                            'message': response['message'],
                            'sticky': False,
                            'type': 'warning',
                            'next': {
                                'type': 'ir.actions.act_window_close',
                            }
                        }
                    }
                    return action


# class AccountMoveLine(models.Model):
#     _inherit = 'account.move.line'
#
#     def _check_amls_exigibility_for_reconciliation(self, shadowed_aml_values=None):
#         """ Ensure the current journal items are eligible to be reconciled together.
#         :param shadowed_aml_values: A mapping aml -> dictionary to replace some original aml values to something else.
#                                     This is usefull if you want to preview the reconciliation before doing some changes
#                                     on amls like changing a date or an account.
#         """
#         if not self:
#             return
#
#         if any(aml.reconciled for aml in self):
#             raise UserError(_("You are trying to reconcile some entries that are already reconciled."))
#         if any(aml.parent_state not in ['posted', 'sent'] for aml in self):
#             raise UserError(_("You can only reconcile posted entries."))
#         accounts = self.mapped(lambda x: x._get_reconciliation_aml_field_value('account_id', shadowed_aml_values))
#         if len(accounts) > 1:
#             raise UserError(_(
#                 "Entries are not from the same account: %s",
#                 ", ".join(accounts.mapped('display_name')),
#             ))
#         if len(self.company_id.root_id) > 1:
#             raise UserError(_(
#                 "Entries don't belong to the same company: %s",
#                 ", ".join(self.company_id.mapped('display_name')),
#             ))
#         if not accounts.reconcile and accounts.account_type not in ('asset_cash', 'liability_credit_card'):
#             raise UserError(_(
#                 "Account %s does not allow reconciliation. First change the configuration of this account "
#                 "to allow it.",
#                 accounts.display_name,
#             ))

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    sale_order_reference = fields.Char()