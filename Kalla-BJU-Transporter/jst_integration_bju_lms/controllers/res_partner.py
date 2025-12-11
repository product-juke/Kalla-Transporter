# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import requests

class ResPartner(http.Controller):
    @http.route('/post/customer-callback', type='json', auth='public', methods=['POST'], csrf=False)
    def post_customer_callback(self, **kw):
        data = request.dispatcher.jsonrequest
        partner_id = request.env['res.partner'].sudo().search([('vat', '=', data['accountNumber'])])
        if len(partner_id) == 1:
            status = "success"
            message = "Callback Received Successfully"
            data_received = {
                "accountNumber": partner_id.vat
            }
            partner_id.oracle_sync_statusCode = 200
            partner_id.oracle_sync_message = message
            partner_id.oracle_sync_date = fields.Datetime.now()
        elif len(partner_id) > 1:
            status = "failed"
            message = "There are Double Account Number!"
            data_received = {
                "accountNumber": partner_id.vat
            }
        else:
            status = "failed"
            message = "Account Number is not exist in Odoo!"
            data_received = {
                "accountNumber": "null"
            }

        response = {
            "status": status,
            "message": message,
            "data_received": data_received
        }
        return response