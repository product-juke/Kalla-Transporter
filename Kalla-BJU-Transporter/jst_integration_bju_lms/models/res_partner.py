from odoo import fields, models, api, _
from odoo.exceptions import UserError
import json, time, http.client
from datetime import timedelta
import socket
import http.client
import urllib.parse

import logging


_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'portfolio.view.mixin']

    invoice_policy = fields.Selection([
        ("order", "CBD"),
        ("delivery", "TOP")
    ], string='Invoice Policy')
    contact_person = fields.Char()
    no_fax = fields.Char('No Fax')
    date_of_birth = fields.Date('Date of Birth')
    place_of_birth = fields.Char('Place of Birth')
    oracle_sync_statusCode = fields.Char('Status Code', copy=False, tracking=True)
    oracle_sync_message = fields.Char('Message', copy=False, tracking=True)
    oracle_sync_full_message = fields.Text('Full Message', copy=False, tracking=True)
    oracle_sync_date = fields.Datetime('Sync Date', copy=False, tracking=True)
    Supplier = fields.Char('Oracle Supplier')
    SupplierSite = fields.Char('Oracle Supplier Site')

    def format_error_messages(self, json_data):
        """
        Format pesan error dengan split koma dan join dengan koma
        """
        try:
            # Cek apakah json_data kosong atau None
            if not json_data:
                _logger.info("On Send Partner -> No error message available")

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
            _logger.info(f"On Send Partner -> Invalid JSON format: {str(json_data)}")
            return '-'

        except Exception as e:
            # Tangani error lainnya
            _logger.info(f"On Send Partner -> Error processing data: {str(e)} - Data: {str(json_data)}")
            return '-'

    def split_name(self, name):
        # Your splitting logic here
        if not name:
            return '-', '-'

        name_parts = name.strip().split()
        if len(name_parts) == 1:
            return name_parts[0], '-'
        elif len(name_parts) >= 2:
            firstname = name_parts[0]
            lastname = ' '.join(name_parts[1:])
            return firstname, lastname
        else:
            return '-', '-'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            sync_customer_to_oracle = rec.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.sync_customer_to_oracle')
            use_queue_customer = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.use_queue_customer')
            if sync_customer_to_oracle:
                if rec:
                    if use_queue_customer:
                        _logger.info(f"On Sync Customer to Middleware with Queue {rec.is_vendor}, {rec.is_driver}, {rec.id}")
                        rec.with_delay().send_customer(rec)
                    else:
                        _logger.info(f"On Sync Customer to Middleware {rec.is_vendor}, {rec.is_driver}, {rec.id}")
                        rec.send_customer(rec)
        return records

    def send_customer(self, rec):
        is_lms = self.is_lms(self.env.company.portfolio_id.name)
        is_fms = self.is_fms(self.env.company.portfolio_id.name)
        has_relation_to_driver = self.env['hr.employee'].search([
            ('work_contact_id', '=', rec.id),
            ('job_title', 'in', ['Driver', 'Drivers', 'driver', 'drivers']),
        ], limit=1)
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        clientId = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientId')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')
        route = '/oracle-integration/api/supplier' if rec.is_vendor or has_relation_to_driver else '/oracle-integration/api/customer'

        portfolio = 'transporter'
        datas = {
            "accountNumber": rec.vat,
            "accountEstablishedDate": rec.create_date.strftime('%Y-%m-%d'),
            "accountAddressSet": "KALLA_CUSTOMER_SET",
            "customerNumber": rec.vat,
            # "customerType": "ORG" if rec.company_type == 'company' else "PERSON",
            "customerType": "ORG" if not rec.is_company else "PERSON",
            "customerName": rec.name,
            "dateOfBirth": rec.date_of_birth.strftime('%Y-%m-%d') if rec.date_of_birth else (fields.Date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
            "placeOfBirth": rec.place_of_birth if rec.place_of_birth else "",
            "phoneNumber": rec.mobile,
            "siteName": rec.website,
            "address1": rec.street if rec.street else "",
            # "address2": rec.street2 if rec.street2 else "",
            "country": "ID",
            "purpose": "BILL_TO"
        }

        _logger.info(f"Partner is Vendor: {rec.is_vendor}")
        _logger.info(f"Partner is Driver: {rec.is_driver}, {has_relation_to_driver}, {rec.id}")
        _logger.info(f"Partner is Customer: {rec.is_customer}")

        if rec.is_vendor or has_relation_to_driver:
            firstname, lastname = self.split_name(rec.name)
            supplier_product_service = self.env['supplier.product.service'].search([
                ('is_active', '=', True)
            ], limit=1)

            datas = {
                "Supplier": rec.name,
                "BusinessRelationshipCode": "SPEND_AUTHORIZED",
                "TaxOrganizationTypeCode": "INDIVIDUAL",
                "TaxpayerCountry": "Indonesia",
                "TaxpayerCountryCode": "ID",
                "TaxpayerId": rec.vat,
                "SupplierType" : "Supplier",
                "addresses": {
                    "CountryCode":"ID",
                    "AddressName": rec.contact_address_complete,
                    "AddressPurposeOrderingFlag": "Y",
                    "AddressPurposeRemitToFlag": "Y",
                    "AddressPurposeRFQOrBiddingFlag": "Y",
                    "AddressLine1" : rec.street
                },
                "contacts": {
                    "Email": rec.email or "",
                    "FirstName": firstname,
                    "LastName": lastname
                },
                "sites": {
                    "SupplierSite": rec.supplier_site,
                    "ProcurementBU": "Bumi Jasa Utama",
                    "SupplierAddressName": rec.contact_address_complete,
                    "SitePurposePurchasingFlag":"Y",
                    "SitePurposePayFlag":"Y",
                    "assignments":{
                        "ClientBU":"Bumi Jasa Utama",
                        "BillToBU":"Bumi Jasa Utama"
                    }
                },
            }

            if not supplier_product_service: # Set default jika tidak ada record di table supplier_product_service
                datas['productsAndServices'] = {
                    "ProductsServicesCategoryId": "300000067419451",
                    "CategoryName": "A_PURCHASING_GOODS",
                    "CategoryType": "BROWSING"
                }
            else:
                datas['productsAndServices'] = {
                    "ProductsServicesCategoryId": supplier_product_service.product_service_category_id,
                    "CategoryName": supplier_product_service.category_name,
                    "CategoryType": supplier_product_service.category_type,
                }

        if is_fms:
            portfolio = 'frozen'
            datas = {
                "accountNumber": rec.vat,
                "accountEstablishedDate": rec.create_date.strftime('%Y-%m-%d'),
                "accountAddressSet": "KALLA_CUSTOMER_SET",
                "customerNumber": rec.vat,
                "customerType": "ORG" if rec.company_type == 'company' else "PERSON",
                "customerName": rec.name,
                "dateOfBirth": rec.date_of_birth.strftime('%Y-%m-%d') if rec.date_of_birth else (
                            fields.Date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "placeOfBirth": rec.place_of_birth if rec.place_of_birth else "",
                "phoneNumber": rec.mobile,
                "address1": rec.street if rec.street else "",
                "address2": rec.street2 if rec.street2 else "",
                "country": "ID",
                "purpose": "BILL_TO"
            }

        try:
            conn = http.client.HTTPSConnection(url, port or None)
            _logger.info(f"Connection for: {url}{route} with port {port or '-'} -> {conn}")

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

            _logger.info(f"Status Code: {res.status}")
            _logger.info(f"Response: {res.reason}")
            _logger.info(f"Response Body: {res_body}")
            # _logger.info(Headers:, headers)
            _logger.info(f"Payload Partner =>  {payload}")

            rec.oracle_sync_statusCode = res.status
            rec.oracle_sync_message = res.reason
            if res_body:
                rec.oracle_sync_full_message = self.format_error_messages(res_body)
            rec.oracle_sync_date = fields.Datetime.now()

            if res.status and res.status in (200, 202, '200', '202', 400, '400', 422, '422'):
                self.env['middleware.response.request.log'].create({
                    'res_id': self.id,
                    'name': self.name,
                    'res_model': 'res.partner',
                    'sync_status_code': int(res.status),
                    'sync_message': self.format_error_messages(res_body) if res_body else res.reason,
                    'payload_sent': str(payload),
                    'portfolio': portfolio,
                    'description': 'Send Supplier' if portfolio != 'frozen' and rec.is_vendor else 'Send Customer'
                })
        except socket.gaierror as e:
            _logger.info(f"Error => {e}")
            # raise UserError(
            #     f"Network error: Cannot resolve hostname. Check your internet connection and the target URL.")
        except Exception as e:
            _logger.info(f"Error Exception => {e}")
            # raise UserError(f"Connection failed: {str(e)}")

    def button_send_customer(self):
        if self.is_vendor and not self.vat:
            raise UserError("Tax ID wajib diisi sebelum melakukan sinkronisasi!")

        is_lms = self.is_lms(self.env.company.portfolio_id.name)
        is_fms = self.is_fms(self.env.company.portfolio_id.name)
        has_relation_to_driver = self.env['hr.employee'].search([
            ('work_contact_id', '=', self.id),
            ('job_title', 'in', ['Driver', 'Drivers', 'driver', 'drivers']),
        ], limit=1)
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        clientId = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.clientId')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')
        route = '/oracle-integration/api/supplier' if self.is_vendor or has_relation_to_driver else '/oracle-integration/api/customer'

        portfolio = 'transporter'
        datas = {
            "accountNumber": self.vat,
            "accountEstablishedDate": self.create_date.strftime('%Y-%m-%d'),
            "accountAddressSet": "KALLA_CUSTOMER_SET",
            "customerNumber": self.vat,
            "customerType": "ORG" if self.company_type == 'company' else "PERSON",
            "customerName": self.name,
            "dateOfBirth": self.date_of_birth.strftime('%Y-%m-%d') if self.date_of_birth else (fields.Date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
            "placeOfBirth": self.place_of_birth if self.place_of_birth else "",
            "phoneNumber": self.mobile,
            "siteName": self.website if self.website else "",
            "address1": self.street if self.street else "",
            # "address2": self.street2 if self.street2 else "",
            "country": "ID",
            "purpose": "BILL_TO"
        }

        _logger.info(f"Partner is Vendor: {self.is_vendor}")
        _logger.info(f"Partner is Driver: {self.is_driver}, {has_relation_to_driver}, {self.id}")
        _logger.info(f"Partner is Customer: {self.is_customer}")

        if self.is_vendor or has_relation_to_driver:
            firstname, lastname = self.split_name(self.name)
            supplier_product_service = self.env['supplier.product.service'].search([
                ('is_active', '=', True)
            ], limit=1)

            datas = {
                "Supplier": self.name,
                "BusinessRelationshipCode": "SPEND_AUTHORIZED",
                "TaxOrganizationTypeCode": "INDIVIDUAL",
                "TaxpayerCountry": "Indonesia",
                "TaxpayerCountryCode": "ID",
                "TaxpayerId": self.vat,
                "SupplierType" : "Supplier",
                "addresses": {
                    "CountryCode":"ID",
                    "AddressName": self.contact_address_complete,
                    "AddressPurposeOrderingFlag": "Y",
                    "AddressPurposeRemitToFlag": "Y",
                    "AddressPurposeRFQOrBiddingFlag": "Y",
                    "AddressLine1" : self.street
                },
                "contacts": {
                    "Email": self.email or "",
                    "FirstName": firstname,
                    "LastName": lastname
                },
                "sites": {
                    "SupplierSite": self.supplier_site,
                    "ProcurementBU": "Bumi Jasa Utama",
                    "SupplierAddressName": self.contact_address_complete,
                    "SitePurposePurchasingFlag":"Y",
                    "SitePurposePayFlag":"Y",
                    "assignments":{
                        "ClientBU":"Bumi Jasa Utama",
                        "BillToBU":"Bumi Jasa Utama"
                    }
                },
            }

            if not supplier_product_service: # Set default jika tidak ada record di table supplier_product_service
                datas['productsAndServices'] = {
                    "ProductsServicesCategoryId": "300000067419451",
                    "CategoryName": "A_PURCHASING_GOODS",
                    "CategoryType": "BROWSING"
                }
            else:
                datas['productsAndServices'] = {
                    "ProductsServicesCategoryId": supplier_product_service.product_service_category_id,
                    "CategoryName": supplier_product_service.category_name,
                    "CategoryType": supplier_product_service.category_type,
                }

        if is_fms:
            portfolio = 'frozen'
            datas = {
                "accountNumber": self.vat,
                "accountEstablishedDate": self.create_date.strftime('%Y-%m-%d'),
                "accountAddressSet": "KALLA_CUSTOMER_SET",
                "customerNumber": self.vat,
                "customerType": "ORG" if self.company_type == 'company' else "PERSON",
                "customerName": self.name,
                "dateOfBirth": self.date_of_birth.strftime('%Y-%m-%d') if self.date_of_birth else (
                            fields.Date.today() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "placeOfBirth": self.place_of_birth if self.place_of_birth else "",
                "phoneNumber": self.mobile,
                "address1": self.street if self.street else "",
                "address2": self.street2 if self.street2 else "",
                "country": "ID",
                "purpose": "BILL_TO"
            }

        is_resend = self.env.context.get('is_resend')
        if is_resend:
            _logger.info('On Resend Customer to Oracle')
            datas['resend'] = True

        res_body = None

        try:
            conn = http.client.HTTPSConnection(url, port or None)
            _logger.info(f"Connection for: {url}{route} with port {port or '-'} -> {conn}")

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

            _logger.info(f"Status Code: {res.status}")
            _logger.info(f"Response: {res.reason}")
            _logger.info(f"Response Body: {res_body}")
            # _logger.info(Headers:, headers)
            _logger.info(f"Payload Partner =>  {payload}")

            self.oracle_sync_statusCode = res.status
            self.oracle_sync_message = res.reason
            if res_body:
                self.oracle_sync_full_message = self.format_error_messages(res_body)
            self.oracle_sync_date = fields.Datetime.now()

            if res.status and res.status in (200, 202, '200', '202', 400, '400', 422, '422'):
                self.env['middleware.response.request.log'].create({
                    'res_id': self.id,
                    'name': self.name,
                    'res_model': 'res.partner',
                    'sync_status_code': int(res.status),
                    'sync_message': self.format_error_messages(res_body) if res_body else res.reason,
                    'payload_sent': str(payload),
                    'portfolio': portfolio,
                    'description': 'Send Supplier' if portfolio != 'frozen' and self.is_vendor else 'Send Customer'
                })
        except socket.gaierror as e:
            _logger.info(f"Error => {e}")
            raise UserError(
                f"Network error: Cannot resolve hostname. Check your internet connection and the target URL.")
        except Exception as e:
            if res_body:
                self.oracle_sync_full_message = self.format_error_messages(res_body)
            raise UserError(f"Connection failed: {str(e)}. {str(res_body)}")

    def action_get_customer(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        conn = http.client.HTTPSConnection(url, port or None)
        payload = ''
        headers = {
            'User-Agent': UserAgent,
            'Authorization': Authorization
        }

        # Default untuk customer
        route = '/oracle-integration/api/customer'
        param_value = self.vat

        # Jika vendor/supplier
        if self.is_vendor:
            route = '/oracle-integration/api/supplier'
            param_value = self.name

        # URL encode parameter untuk menangani spasi dan karakter khusus
        encoded_param = urllib.parse.quote(str(param_value), safe='')
        full_url = f"{route}/{encoded_param}"

        _logger.info(f"Original parameter: {param_value}")
        _logger.info(f"Encoded parameter: {encoded_param}")
        _logger.info(f"Full URL: {full_url}")

        conn.request("GET", full_url, payload, headers)
        res = conn.getresponse()
        data = res.read()
        data_decoded = data.decode("utf-8")

        try:
            response = json.loads(data_decoded)
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error: {e}")
            _logger.error(f"Response body: {data_decoded}")
            response = {'message': 'Invalid JSON response from server'}

        _logger.info(f"Status Code: {res.status}")
        _logger.info(f"Response: {res.reason}")
        _logger.info(f"Response Body: {data_decoded}")
        _logger.info(f"Payload: {payload}")

        # Handling response message
        if 'flag' in response:
            if response['flag'] not in ['ADD', 'SENT']:
                message = f"{response['flag']} ===> {response.get('messages', '')}"
            else:
                message = response['flag']
        else:
            message = response.get('message', 'Unknown response')

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
