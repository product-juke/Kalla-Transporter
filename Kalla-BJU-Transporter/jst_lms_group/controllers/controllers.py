# -*- coding: utf-8 -*-
# from odoo import http


# class JstLmsGroup(http.Controller):
#     @http.route('/jst_lms_group/jst_lms_group', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_lms_group/jst_lms_group/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_lms_group.listing', {
#             'root': '/jst_lms_group/jst_lms_group',
#             'objects': http.request.env['jst_lms_group.jst_lms_group'].search([]),
#         })

#     @http.route('/jst_lms_group/jst_lms_group/objects/<model("jst_lms_group.jst_lms_group"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_lms_group.object', {
#             'object': obj
#         })

