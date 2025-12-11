from odoo import fields, models, api, _
import hashlib, json, http.client, random
from datetime import timedelta
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_due = fields.Monetary(currency_field='currency_id', compute='compute_amount_due', store=True)
    invoice_date_due = fields.Date(compute='compute_invoice_date_due', store=True)

    @api.depends('invoice_ids', 'invoice_ids.amount_residual')
    def compute_amount_due(self):
        for rec in self:
            rec.amount_due = 0
            if rec.invoice_ids:
                rec.amount_due = sum(rec.invoice_ids.filtered(lambda inv: inv.state == 'posted').mapped('amount_residual'))

    @api.depends('date_order', 'payment_term_id')
    def compute_invoice_date_due(self):
        for rec in self:
            rec.invoice_date_due = False
            if rec.date_order and rec.payment_term_id:
                base_date = (rec.date_order + timedelta(hours=7)).date()

                if rec.payment_term_id.name in ['IMMEDIATE', 'Immediate']:
                    rec.invoice_date_due = base_date
                else:
                    # Use payment term's actual configuration
                    days = 0
                    try:
                        if rec.payment_term_id.line_ids:
                            # Try nb_days first (standard field)
                            if hasattr(rec.payment_term_id.line_ids[0], 'nb_days'):
                                days = rec.payment_term_id.line_ids[0].nb_days
                            elif hasattr(rec.payment_term_id.line_ids[0], 'days'):
                                days = rec.payment_term_id.line_ids[0].days
                    except (IndexError, AttributeError):
                        # Fallback: extract from name if payment term lines fail
                        import re
                        days_match = re.search(r'\d+', rec.payment_term_id.name)
                        if days_match:
                            days = int(days_match.group())

                    rec.invoice_date_due = base_date + timedelta(days=days)

    def action_get_payment_cbd(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        route = '/receipt'
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        sha256Token = self.generate_sha256_token()
        clientIdReceipt = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientIdReceipt')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        conn = http.client.HTTPSConnection(url, port)
        payload = ''
        headers = {
            'clientId': clientIdReceipt,
            'Authorization': sha256Token,
            'User-Agent': UserAgent
        }

        if self.state in ['sale', 'auto_gin'] and self.invoice_policy == 'order' and self.payment_status != 'fully_paid':
            conn.request("GET", '%s/%s' % (route, self.oracle_number), payload, headers)
            res = conn.getresponse()
            data = res.read()
            data = data.decode("utf-8")
            response = json.loads(data)

            if 'data' in response:
                for receipt in response['data']:
                    if 'G_2' in receipt:
                        payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['RECEIPT_NUMBER']), ('amount', '=', receipt['G_2']['AMOUNT_APPLIED']), ('CASH_RECEIPT_ID', '=', receipt['CASH_RECEIPT_ID'])])
                    else:
                        payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['RECEIPT_NUMBER']), ('amount', '=', receipt['AMOUNT']), ('CASH_RECEIPT_ID', '=', receipt['CASH_RECEIPT_ID'])])

                    if payment_id:
                        if receipt['STATUS'] == 'REV' and payment_id.state == 'posted':
                            payment_id.action_draft()
                            payment_id.action_cancel()
                        else:
                            order_id = self.env['sale.order'].search([('state', 'in', ['sale', 'auto_gin']), ('name', '=', payment_id.ref)])
                            if order_id:
                                payment_id.sale_id = order_id.id
                    if not payment_id:
                        if receipt['STATUS'] == 'UNID':
                            raise UserError(_("The Oracle payment process is not complete!"))
                        elif receipt['STATUS'] in ['APP', 'UNAPP']:
                            if 'G_2' not in receipt:
                                raise UserError(_("Payment status Unapply"))
                            else:
                                payment_id = self.create_payment(receipt)
                                if float(receipt['G_2']['AMOUNT_APPLIED']) >= self.amount_total:
                                    payment_id.sale_id = self.id
                                    self.payment_status = 'fully_paid'
                                elif 0 < float(receipt['G_2']['AMOUNT_APPLIED']) < self.amount_total:
                                    payment_id.sale_id = self.id
                                    self.payment_status = 'partial_paid'
            else:
                if 'success' in response:
                    if response['success'] == False:
                        self.failed_payment_ar_cbd = True
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

    def generate_sha256_token(self):
        today = str(fields.Date.today())
        clientIdReceipt = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientIdReceipt')
        input_string = "%s%s" % (clientIdReceipt, today.replace("-", ""))
        sha_signature = hashlib.sha256(input_string.encode()).hexdigest()
        return sha_signature

    def ir_cron_generate_sha256_token(self):
        sha256Token = self.env['ir.config_parameter'].sudo().search([('key', '=', 'jst_integration_bju.sha256Token')])
        if not sha256Token:
            self.env['ir.config_parameter'].set_param('jst_integration_bju.sha256Token', self.generate_sha256_token())
        else:
            sha256Token.value = self.generate_sha256_token()

    def ir_cron_action_get_payment_cbd(self, limit=100):
        domain = [
            ('invoice_policy', '=', 'order'),
            ('state', 'in', ['sale', 'auto_gin']),
            ('payment_status', '=', 'not_paid')
        ]
        if self._context.get('active_ids') and self._context.get('active_model') == self._name:
            orders = self.env['sale.order'].search(domain + [('id', 'in', self._context.get('active_ids'))])
        else:
            orders = self.env['sale.order'].search(domain, order='invoice_date_due asc', limit=limit)
        if orders:
            for so in orders:
                so.with_delay().get_payment_cbd()

                if so.invoice_ids:
                    inv_posted = so.invoice_ids.filtered(lambda x: x.state == 'posted')
                    so.amount_due = sum(inv_posted.mapped('amount_residual'))

                    payment_id = self.env['account.payment.oracle'].search([('name', '=', so.name)])
                    if payment_id:
                        payment_id.type = 'ar_cbd'
                        if so.amount_due == 0:
                            payment_id.status = 'fully_paid'
                        elif so.amount_due < so.amount_total:
                            payment_id.status = 'partial_paid'
                        else:
                            payment_id.status = 'not_paid'
                    else:
                        payment_id = self.env['account.payment.oracle'].create({
                            'name': so.name,
                            'type': 'ar_cbd'
                        })
                        if so.amount_due == 0:
                            payment_id.status = 'fully_paid'
                        elif so.amount_due < so.amount_total:
                            payment_id.status = 'partial_paid'
                        else:
                            payment_id.status = 'not_paid'
                else:
                    payment_id = self.env['account.payment.oracle'].search([('name', '=', so.name)])
                    if payment_id:
                        payment_id.status = 'nothing'
                    else:
                        payment_id = self.env['account.payment.oracle'].create({
                            'name': so.name,
                            'type': 'ar_cbd'
                        })
                        payment_id.status = 'nothing'
                self.env.cr.commit()

    def get_payment_cbd(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        route = '/receipt'
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        sha256Token = self.generate_sha256_token()
        clientIdReceipt = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientIdReceipt')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        conn = http.client.HTTPSConnection(url, port)
        payload = ''
        headers = {
            'clientId': clientIdReceipt,
            'Authorization': sha256Token,
            'User-Agent': UserAgent
        }

        for sale_order in self:
            conn.request("GET", '%s/%s' % (route, sale_order.name), payload, headers)
            res = conn.getresponse()
            data = res.read()
            data = data.decode("utf-8")
            response = json.loads(data)

            if 'data' in response:
                for receipt in response['data']:
                    if 'G_2' in receipt:
                        payment_id = self.env['account.payment'].search([('state', 'in', ['posted','cancel']), ('ref', '=', receipt['RECEIPT_NUMBER']), ('amount', '=', receipt['G_2']['AMOUNT_APPLIED']), ('CASH_RECEIPT_ID', '=', receipt['CASH_RECEIPT_ID'])])
                    else:
                        payment_id = self.env['account.payment'].search([('state', 'in', ['posted','cancel']), ('ref', '=', receipt['RECEIPT_NUMBER']), ('amount', '=', receipt['AMOUNT']), ('CASH_RECEIPT_ID', '=', receipt['CASH_RECEIPT_ID'])])

                    if payment_id:
                        if receipt['STATUS'] == 'REV' and payment_id.state == 'posted':
                            payment_id.action_draft()
                            payment_id.action_cancel()
                        else:
                            order_id = self.env['sale.order'].search([('state', 'in', ['sale', 'auto_gin']), ('name', '=', payment_id.ref)])
                            if order_id:
                                payment_id.sale_id = order_id.id
                    if not payment_id:
                        if receipt['STATUS'] == 'UNID':
                            raise UserError(_("The Oracle payment process is not complete!"))
                        elif receipt['STATUS'] in ['APP', 'UNAPP']:
                            if 'G_2' not in receipt:
                                raise UserError(_("Payment status Unapply"))
                            else:
                                payment_id = self.create_payment_cron(receipt, sale_order)
                                if float(receipt['G_2']['AMOUNT_APPLIED']) >= sale_order.amount_total:
                                    payment_id.sale_id = sale_order.id
                                    sale_order.payment_status = 'fully_paid'
                                elif 0 < float(receipt['G_2']['AMOUNT_APPLIED']) < sale_order.amount_total:
                                    payment_id.sale_id = sale_order.id
                                    sale_order.payment_status = 'partial_paid'
            sale_order.env.cr.commit()

    def create_payment(self, receipt):
        journal_id = self.env['account.journal'].search([('bank_account_id.acc_holder_name', '=', receipt['G_2']['BANK_ACCOUNT_NAME'])], limit=1)
        if not journal_id:
            raise ValidationError(_("Bank Account Name : %s does'nt exist!" % receipt['G_2']['BANK_ACCOUNT_NAME']))
        else:
            payment_register = self.env['account.payment'].create({
                'partner_id': self.partner_id.id,
                'journal_id': journal_id.id,
                'company_id': journal_id.company_id.id,
                'amount': receipt['G_2']['AMOUNT_APPLIED'],
                'date': fields.Date.today(),
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'ref': receipt['RECEIPT_NUMBER'],
            })
            payment_register.action_post()
            payment_register.CASH_RECEIPT_ID = receipt['CASH_RECEIPT_ID']
            payment_register.env.cr.commit()
            return payment_register

    def create_payment_cron(self, receipt, order):
        journal_id = self.env['account.journal'].search([('bank_account_id.acc_holder_name', '=', receipt['G_2']['BANK_ACCOUNT_NAME'])], limit=1)
        if not journal_id:
            raise ValidationError(_("Bank Account Name : %s does'nt exist!" % receipt['G_2']['BANK_ACCOUNT_NAME']))
        else:
            payment_register = self.env['account.payment'].create({
                'partner_id': order.partner_id.id,
                'journal_id': journal_id.id,
                'company_id': journal_id.company_id.id,
                'amount': receipt['G_2']['AMOUNT_APPLIED'],
                'date': fields.Date.today(),
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'ref': receipt['RECEIPT_NUMBER'],
            })
            payment_register.action_post()
            payment_register.CASH_RECEIPT_ID = receipt['CASH_RECEIPT_ID']
            payment_register.env.cr.commit()
            return payment_register
