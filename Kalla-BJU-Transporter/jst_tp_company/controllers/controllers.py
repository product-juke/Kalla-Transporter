# -*- coding: utf-8 -*-
# from odoo import http


# class JstTpCompany(http.Controller):
#     @http.route('/jst_tp_company/jst_tp_company', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_tp_company/jst_tp_company/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_tp_company.listing', {
#             'root': '/jst_tp_company/jst_tp_company',
#             'objects': http.request.env['jst_tp_company.jst_tp_company'].search([]),
#         })

#     @http.route('/jst_tp_company/jst_tp_company/objects/<model("jst_tp_company.jst_tp_company"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_tp_company.object', {
#             'object': obj
#         })

