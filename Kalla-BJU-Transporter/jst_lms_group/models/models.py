# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class jst_lms_group(models.Model):
#     _name = 'jst_lms_group.jst_lms_group'
#     _description = 'jst_lms_group.jst_lms_group'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

