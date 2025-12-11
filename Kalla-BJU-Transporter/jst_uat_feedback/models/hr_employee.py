from odoo import models, fields, api, _

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    driver_status = fields.Selection([
        ('helper', 'Helper'),
        ('driver_utama', 'Driver Utama'),
        ('driver_pengganti', 'Driver Pengganti'),
    ])