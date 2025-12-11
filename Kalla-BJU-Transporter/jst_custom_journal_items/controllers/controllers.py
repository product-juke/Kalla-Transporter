# -*- coding: utf-8 -*-
# from odoo import http


# class JstCustomJournalItems(http.Controller):
#     @http.route('/jst_custom_journal_items/jst_custom_journal_items', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_custom_journal_items/jst_custom_journal_items/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_custom_journal_items.listing', {
#             'root': '/jst_custom_journal_items/jst_custom_journal_items',
#             'objects': http.request.env['jst_custom_journal_items.jst_custom_journal_items'].search([]),
#         })

#     @http.route('/jst_custom_journal_items/jst_custom_journal_items/objects/<model("jst_custom_journal_items.jst_custom_journal_items"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_custom_journal_items.object', {
#             'object': obj
#         })

