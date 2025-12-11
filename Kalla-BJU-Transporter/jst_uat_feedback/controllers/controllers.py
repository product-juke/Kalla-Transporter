# -*- coding: utf-8 -*-
# from odoo import http


# class JstUatFeedback(http.Controller):
#     @http.route('/jst_uat_feedback/jst_uat_feedback', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_uat_feedback/jst_uat_feedback/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_uat_feedback.listing', {
#             'root': '/jst_uat_feedback/jst_uat_feedback',
#             'objects': http.request.env['jst_uat_feedback.jst_uat_feedback'].search([]),
#         })

#     @http.route('/jst_uat_feedback/jst_uat_feedback/objects/<model("jst_uat_feedback.jst_uat_feedback"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_uat_feedback.object', {
#             'object': obj
#         })

