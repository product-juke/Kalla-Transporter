# -*- coding: utf-8 -*-
# from odoo import http


# class JstTpDeliveryDocument(http.Controller):
#     @http.route('/jst_tp_delivery_document/jst_tp_delivery_document', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_tp_delivery_document/jst_tp_delivery_document/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_tp_delivery_document.listing', {
#             'root': '/jst_tp_delivery_document/jst_tp_delivery_document',
#             'objects': http.request.env['jst_tp_delivery_document.jst_tp_delivery_document'].search([]),
#         })

#     @http.route('/jst_tp_delivery_document/jst_tp_delivery_document/objects/<model("jst_tp_delivery_document.jst_tp_delivery_document"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_tp_delivery_document.object', {
#             'object': obj
#         })

