# -*- coding: utf-8 -*-
# from odoo import http


# class JstTpAccountingReport(http.Controller):
#     @http.route('/jst_tp_accounting_report/jst_tp_accounting_report', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_tp_accounting_report/jst_tp_accounting_report/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_tp_accounting_report.listing', {
#             'root': '/jst_tp_accounting_report/jst_tp_accounting_report',
#             'objects': http.request.env['jst_tp_accounting_report.jst_tp_accounting_report'].search([]),
#         })

#     @http.route('/jst_tp_accounting_report/jst_tp_accounting_report/objects/<model("jst_tp_accounting_report.jst_tp_accounting_report"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_tp_accounting_report.object', {
#             'object': obj
#         })

