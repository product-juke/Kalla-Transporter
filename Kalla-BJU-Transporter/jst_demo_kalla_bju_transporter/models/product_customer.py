from odoo import fields, models, api


class ProductCustomer(models.Model):
    _name = 'product.customer'
    _rec_name = 'name'
    _description = 'Product Customer'

    name = fields.Char(string='Product Customer', required=True)