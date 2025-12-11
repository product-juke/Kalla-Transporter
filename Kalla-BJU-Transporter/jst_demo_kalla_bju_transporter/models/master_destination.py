from odoo import fields, models, api


class MasterDestination(models.Model):

    _name = 'master.destination'
    _rec_name = 'name'
    _description = 'Master Destination'

    name = fields.Char()