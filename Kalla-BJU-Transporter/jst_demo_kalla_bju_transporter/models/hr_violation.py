from odoo import fields, models, api

class HrViolation(models.Model):
    _name = 'hr.violation'
    _rec_name = 'violation'
    _description = 'Violation'

    type_violation = fields.Selection([('behavior', 'Behavior'), ('performance', 'Performance')], string='Tipe Pelanggaran')
    violation = fields.Char(string='Jenis Pelanggaran', required=True)
