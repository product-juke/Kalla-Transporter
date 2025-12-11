# -*- coding: utf-8 -*-
from odoo import fields, models, api


class DeliveryCategory(models.Model):
    _name = 'delivery.category'
    _rec_name = 'name'
    _description = 'Delivery Category'

    name = fields.Char()
    product_category_id = fields.Many2one('product.category', 'Product Category')

