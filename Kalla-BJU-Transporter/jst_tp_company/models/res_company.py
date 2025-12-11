from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    portfolio_id = fields.Many2one('bju.portfolio', 'Portfolio')



