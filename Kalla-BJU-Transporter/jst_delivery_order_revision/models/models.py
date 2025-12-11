# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class jst_delivery_order_revision(models.Model):
#     _name = 'jst_delivery_order_revision.jst_delivery_order_revision'
#     _description = 'jst_delivery_order_revision.jst_delivery_order_revision'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

