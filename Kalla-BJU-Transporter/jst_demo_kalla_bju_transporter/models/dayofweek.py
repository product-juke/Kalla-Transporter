from odoo import fields, models, api, _


class Dayofweek(models.Model):
    _name = 'dayofweek'
    _rec_name = 'name'
    _description = 'Day Of Week'

    name = fields.Char()