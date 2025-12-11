from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portfolio.view.mixin']

    is_revised_from_do = fields.Boolean()
    ref_so_revision_id = fields.Many2one(comodel_name='sale.order')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_header_from_revision = fields.Boolean()
    prev_bop = fields.Float()

    @api.model_create_multi
    def create(self, vals_list):
        is_from_revision_wizard = self.env.context.get('is_from_revision_wizard')
        if is_from_revision_wizard:
            raise UserError(_(f"Tidak bisa membuat Line melalui form ini."))

        return super(SaleOrderLine, self).create(vals_list)
