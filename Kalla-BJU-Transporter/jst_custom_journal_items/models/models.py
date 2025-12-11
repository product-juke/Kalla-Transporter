# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class jst_custom_journal_items(models.Model):
#     _name = 'jst_custom_journal_items.jst_custom_journal_items'
#     _description = 'jst_custom_journal_items.jst_custom_journal_items'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

