from odoo import fields, models

class UtilizationDetails(models.Model):
    _name = 'utilization.details'
    _description = 'Utilization Details'

    code = fields.Char(string='Code', required=True)
    description = fields.Char(string='Description')
    parent_status = fields.Char(string='Parent Status')
    utilization_status = fields.Char(string='Utilization Status')
    pa = fields.Float(string='PA (%)', digits=(5, 2))