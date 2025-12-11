# -*- coding: utf-8 -*-
# from odoo import http


# class JstHighLevelDashboard(http.Controller):
#     @http.route('/jst_high_level_dashboard/jst_high_level_dashboard', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_high_level_dashboard/jst_high_level_dashboard/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_high_level_dashboard.listing', {
#             'root': '/jst_high_level_dashboard/jst_high_level_dashboard',
#             'objects': http.request.env['jst_high_level_dashboard.jst_high_level_dashboard'].search([]),
#         })

#     @http.route('/jst_high_level_dashboard/jst_high_level_dashboard/objects/<model("jst_high_level_dashboard.jst_high_level_dashboard"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_high_level_dashboard.object', {
#             'object': obj
#         })

