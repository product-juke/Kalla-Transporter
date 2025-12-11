# -*- coding: utf-8 -*-
# from odoo import http


# class JstTpUtilization(http.Controller):
#     @http.route('/jst_tp_utilization/jst_tp_utilization', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_tp_utilization/jst_tp_utilization/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_tp_utilization.listing', {
#             'root': '/jst_tp_utilization/jst_tp_utilization',
#             'objects': http.request.env['jst_tp_utilization.jst_tp_utilization'].search([]),
#         })

#     @http.route('/jst_tp_utilization/jst_tp_utilization/objects/<model("jst_tp_utilization.jst_tp_utilization"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_tp_utilization.object', {
#             'object': obj
#         })

