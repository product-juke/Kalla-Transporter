# models/product_partner_tax.py

from odoo import models, fields, api


class ProductPartnerTax(models.Model):
    _name = 'product.partner.tax'
    _description = 'Product Partner Tax Configuration'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        help='Partner untuk konfigurasi tax khusus'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
        help='Product yang akan dikonfigurasi'
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'product_partner_tax_rel',
        'product_partner_tax_id',
        'tax_id',
        string='Taxes',
        help='Tax yang akan diterapkan untuk partner dan product ini'
    )

    # Optional: tambahkan constraint untuk mencegah duplikasi
    _sql_constraints = [
        ('unique_partner_product', 'unique(partner_id, product_id)',
         'Kombinasi Partner dan Product harus unik!')
    ]