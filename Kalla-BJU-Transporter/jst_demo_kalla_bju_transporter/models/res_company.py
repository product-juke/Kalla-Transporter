from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    company_code = fields.Char(string='Company Code')