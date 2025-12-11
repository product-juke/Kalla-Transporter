# -*- coding: utf-8 -*-
# from odoo import http


# class JstWrapperPostHook(http.Controller):
#     @http.route('/jst_wrapper_post_hook/jst_wrapper_post_hook', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_wrapper_post_hook/jst_wrapper_post_hook/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_wrapper_post_hook.listing', {
#             'root': '/jst_wrapper_post_hook/jst_wrapper_post_hook',
#             'objects': http.request.env['jst_wrapper_post_hook.jst_wrapper_post_hook'].search([]),
#         })

#     @http.route('/jst_wrapper_post_hook/jst_wrapper_post_hook/objects/<model("jst_wrapper_post_hook.jst_wrapper_post_hook"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_wrapper_post_hook.object', {
#             'object': obj
#         })

