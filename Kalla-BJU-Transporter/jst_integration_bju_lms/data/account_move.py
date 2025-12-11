from odoo import fields, models
import hashlib, json, http.client, random
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

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

    def ir_cron_action_get_payment_ar_top(self, limit=100):
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('invoice_policy', '=', 'delivery'),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'not_paid')
        ]
        if self._context.get('active_ids') and self._context.get('active_model') == self._name:
            invoices = self.env['account.move'].search(domain + [('id', 'in', self._context.get('active_ids'))])
        else:
            invoices = self.env['account.move'].search(domain, order='invoice_date_due asc', limit=limit)
        if invoices:
            for am in invoices:
                am.with_delay().get_payment_ar_top()

                payment_id = self.env['account.payment.oracle'].search([('name', '=', am.name)])
                if payment_id:
                    payment_id.type = 'ar_top'
                    if am.amount_residual == 0:
                        payment_id.status = 'fully_paid'
                    elif am.amount_residual < am.amount_total:
                        payment_id.status = 'partial_paid'
                    else:
                        payment_id.status = 'not_paid'

                    so = am.line_ids.sale_line_ids.order_id
                    if so:
                        inv_posted = so.invoice_ids.filtered(lambda x: x.state == 'posted')
                        so.amount_due = sum(inv_posted.mapped('amount_residual'))
                else:
                    payment_id = self.env['account.payment.oracle'].create({
                        'name': am.name,
                        'type': 'ar_top'
                    })
                    if payment_id:
                        if am.amount_residual == 0:
                            payment_id.status = 'fully_paid'
                        elif am.amount_residual < am.amount_total:
                            payment_id.status = 'partial_paid'
                        else:
                            payment_id.status = 'not_paid'

                        so = am.line_ids.sale_line_ids.order_id
                        if so:
                            inv_posted = so.invoice_ids.filtered(lambda x: x.state == 'posted')
                            so.amount_due = sum(inv_posted.mapped('amount_residual'))
                self.env.cr.commit()

    def ir_cron_action_get_payment_ap(self, limit=100):
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'not_paid')
        ]
        if self._context.get('active_ids') and self._context.get('active_model') == self._name:
            invoices = self.env['account.move'].search(domain + [('id', 'in', self._context.get('active_ids'))])
        else:
            invoices = self.env['account.move'].search(domain, order='invoice_date_due asc', limit=limit)
        if invoices:
            for am in invoices:
                am.with_delay().get_payment_ap()

                if am.state == 'posted':
                    payment_id = self.env['account.payment.oracle'].search([('name', '=', am.name)])
                    if payment_id:
                        payment_id.type = 'ap'
                        if am.amount_residual == 0:
                            payment_id.status = 'fully_paid'
                        elif am.amount_residual < am.amount_total:
                            payment_id.status = 'partial_paid'
                        else:
                            payment_id.status = 'not_paid'
                    else:
                        payment_id = self.env['account.payment.oracle'].create({
                            'name': am.name,
                            'type': 'ap'
                        })
                        if payment_id:
                            if am.amount_residual == 0:
                                payment_id.status = 'fully_paid'
                            elif am.amount_residual < am.amount_total:
                                payment_id.status = 'partial_paid'
                            else:
                                payment_id.status = 'not_paid'
                self.env.cr.commit()

    def ir_cron_action_send_invoice(self, limit=100):
        invoices = self.env['account.move'].search([('move_type', '=', 'out_invoice'),
                                                    ('state', '=', 'posted'),
                                                    ('oracle_sync_statusCode', '!=', '202')])
        invoices = random.sample(invoices, limit)
        for inv in invoices:
            inv.with_delay().send_invoice()

    def ir_cron_action_send_invoice_ap(self, limit=100):
        invoices = self.env['account.move'].search([('move_type', '=', 'in_invoice'),
                                                    ('state', '=', 'posted'),
                                                    ('oracle_sync_statusCode', '!=', '202')])
        invoices = random.sample(invoices, limit)
        for inv in invoices:
            inv.with_delay().send_invoice_ap()

    def get_payment_ar_top(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        Authorization = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.Authorization')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')

        conn = http.client.HTTPSConnection(url, port)
        payload = ''
        headers = {
            'Authorization': Authorization,
            'User-Agent': UserAgent
        }
        route = '/receipt_invoice'
        
        for account_move in self:
            conn.request("GET", '%s?number=%s' % (route, account_move.oracle_number), payload, headers)
            res = conn.getresponse()
            data = res.read()
            data = data.decode("utf-8")
            response = json.loads(data)

            if res:
                if self and self.name:
                    _logger.info('INVOICE AP => : %s', self.name)

                _logger.info('Status Code: %s', res.status)
                _logger.info('Response: %s', res.reason)
                _logger.info('Response Body: %s', res.read().decode('utf-8'))
                # _logger.info('Headers: %s', headers)
                _logger.info('Payload => %s', payload)

            if 'data' in response:
                for receipt in response['data']:
                    if 'G_2' not in receipt:
                        account_move.failed_payment_ar_top = True
                    else:
                        account_move.failed_payment_ar_top = False
                        is_array = isinstance(receipt['G_2'], list)
                        if is_array:
                            for G_2 in receipt['G_2']:
                                payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['TRX_NUMBER']), ('CASH_RECEIPT_ID', '=', G_2['CASH_RECEIPT_ID'])])
                                if not payment_id:
                                    if G_2['RECEIPT_STATUS'] in ['APP', 'UNAPP']:
                                        account_move.register_payment_ar_top_list(receipt, G_2)
                                else:
                                    if G_2['RECEIPT_STATUS'] in ['REV', 'STOP'] and G_2['AMOUNT_APPLIED'] > 0:
                                        payment_id.action_draft()
                                        payment_id.action_cancel()
                        else:
                            payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['TRX_NUMBER']), ('CASH_RECEIPT_ID', '=', receipt['G_2']['CASH_RECEIPT_ID'])])
                            if not payment_id:
                                account_move.register_payment_ar_top(receipt)
                    account_move.env.cr.commit()

    def get_payment_ap(self):
        url = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.url_bju')
        port = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.port')
        UserAgent = self.env['ir.config_parameter'].sudo().get_param('jst_integration_bju.UserAgent')
        company_id = self.env['res.company'].sudo().search([('id', '=', self.env.company.id)])

        conn = http.client.HTTPSConnection(url, port)
        payload = ''
        headers = {
            'User-Agent': UserAgent
        }
        route = '/get-payment-ap'

        for account_move in self:
            conn.request("GET", '%s?org=%s&number=%s' % (route, company_id.org, account_move.oracle_number), payload, headers)
            res = conn.getresponse()
            data = res.read()
            data = data.decode("utf-8")
            response = json.loads(data)

            if res:
                if self and self.name:
                    _logger.info('INVOICE AP => : %s', self.name)

                _logger.info('Status Code: %s', res.status)
                _logger.info('Response: %s', res.reason)
                _logger.info('Response Body: %s', res.read().decode('utf-8'))
                # _logger.info('Headers: %s', headers)
                _logger.info('Payload =>  %s', payload)

            if 'data' in response:
                account_move.failed_payment_ap = False
                for receipt in response['data']:
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
                                    account_move.register_payment_ap(G_2)
                    else:
                        payment_id = self.env['account.payment'].search([('state', 'in', ['posted', 'cancel']), ('ref', '=', receipt['G_2']['TRX_NUMBER']), ('amount', '=', receipt['G_2']['AMOUNT_APPLIED']), ('CHECK_ID', '=', receipt['G_2']['CHECK_ID'])])
                        if payment_id:
                            if receipt['G_2']["STATUS_LOOKUP_CODE"] == "VOIDED" and payment_id.state == 'posted':
                                payment_id.action_draft()
                                payment_id.action_cancel()
                        if not payment_id:
                            if receipt['G_2']["STATUS_LOOKUP_CODE"] == "CLEARED":
                                account_move.register_payment_ap(receipt['G_2'])
                    account_move.env.cr.commit()
            else:
                if 'success' in response:
                    if response['success'] == False:
                        account_move.failed_payment_ap = True
            account_move.env.cr.commit()
