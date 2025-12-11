# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class jst_high_level_dashboard(models.Model):
#     _name = 'jst_high_level_dashboard.jst_high_level_dashboard'
#     _description = 'jst_high_level_dashboard.jst_high_level_dashboard'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

