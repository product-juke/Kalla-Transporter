# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import requests

class AccountMove(http.Controller):
    @http.route('/post/invoice-callback', type='json', auth='public', methods=['POST'], csrf=False)
    def post_invoice_callback(self, **kw):
        data = request.dispatcher.jsonrequest
        invoice_id = request.env['account.move'].sudo().search([('move_type', '=', 'out_invoice'),
                                                                ('name', '=', data['invoiceNumber'])])
        if len(invoice_id) == 1:
            status = 'success'
            message = 'Callback Received Successfully'
            data_received = {
                'invoiceNumber': invoice_id.name
            }
            invoice_id.oracle_sync_statusCode = 200
            invoice_id.oracle_sync_message = message
            invoice_id.oracle_sync_date = fields.Datetime.now()
        elif len(invoice_id) > 1:
            status = 'failed'
            message = 'There are Double Invoice Number!'
            data_received = {
                'invoiceNumber': invoice_id[0].name
            }
        else:
            status = 'failed'
            message = 'Invoice is not exist in Odoo!'
            data_received = {
                'invoiceNumber': 'null'
            }

        response = {
            'status': status,
            'message': message,
            'data_received': data_received
        }
        return response

    @http.route('/post/bill-callback', type='json', auth='public', methods=['POST'], csrf=False)
    def post_bill_callback(self, **kw):
        data = request.dispatcher.jsonrequest
        bill_id = request.env['account.move'].sudo().search([('move_type', '=', 'in_invoice'),
                                                                ('name', '=', data['invoiceNumber'])])
        if len(bill_id) == 1:
            status = 'success'
            message = 'Callback Received Successfully'
            data_received = {
                'invoiceNumber': bill_id.name
            }
            bill_id.oracle_sync_statusCode = 200
            bill_id.oracle_sync_message = message
            bill_id.oracle_sync_date = fields.Datetime.now()
        elif len(bill_id) > 1:
            status = 'failed'
            message = 'There are Double Vendor Bill Number!'
            data_received = {
                'invoiceNumber': bill_id[0].name
            }
        else:
            status = 'failed'
            message = 'Vendor Bill is not exist in Odoo!'
            data_received = {
                'invoiceNumber': 'null'
            }

        response = {
            'status': status,
            'message': message,
            'data_received': data_received
        }
        return response