# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    vehicle_id = fields.Many2one('fleet.vehicle')
    vehicle_category_id = fields.Many2one('fleet.vehicle.model.category')
    partner_tax_ids = fields.One2many(
        'product.partner.tax',
        'product_id',
        string='Partner Tax Configuration',
        help='Konfigurasi tax per partner untuk product ini'
    )


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
