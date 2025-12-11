from odoo import fields, models, api


class MasterOrigin(models.Model):

    _name = 'master.origin'
    _rec_name = 'name'
    _description = 'Master Origin'

    name = fields.Char()