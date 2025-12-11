from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    bop_remaining = fields.Float(compute='_compute_bop_remaining')
    driver_bop_balance_ids = fields.One2many(
        'driver.bop.balance',
        'driver_id',
        string='BOP Balance',
        readonly=True
    )

    @api.depends('driver_bop_balance_ids')
    def _compute_bop_remaining(self):
        for rec in self:
            rec.bop_remaining = sum(rec.driver_bop_balance_ids.mapped('remaining_bop'))