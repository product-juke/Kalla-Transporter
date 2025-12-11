# -*- coding: utf-8 -*-
# from odoo import http


# class JstDeliveryOrderRevision(http.Controller):
#     @http.route('/jst_delivery_order_revision/jst_delivery_order_revision', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_delivery_order_revision/jst_delivery_order_revision/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_delivery_order_revision.listing', {
#             'root': '/jst_delivery_order_revision/jst_delivery_order_revision',
#             'objects': http.request.env['jst_delivery_order_revision.jst_delivery_order_revision'].search([]),
#         })

#     @http.route('/jst_delivery_order_revision/jst_delivery_order_revision/objects/<model("jst_delivery_order_revision.jst_delivery_order_revision"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_delivery_order_revision.object', {
#             'object': obj
#         })

