# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class jst_oracle_sync_feedback(models.Model):
#     _name = 'jst_oracle_sync_feedback.jst_oracle_sync_feedback'
#     _description = 'jst_oracle_sync_feedback.jst_oracle_sync_feedback'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

