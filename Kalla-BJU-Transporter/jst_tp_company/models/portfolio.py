from odoo import models, fields, api


class Portfolio(models.Model):
    _name = 'bju.portfolio'

    name = fields.Char('Name')



