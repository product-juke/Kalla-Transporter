from odoo import fields, models, api

class HrInsurance(models.Model):
    _name = 'hr.insurance'
    _rec_name = 'insurance'
    _description = 'Insurance'

    type_insurance = fields.Selection([('kesehatan', 'Kesehatan'), ('ketenagakerjaan', 'Ketenagakerjaan'),('kendaraan', 'Kendaraan')], string='Tipe Asuransi')
    insurance = fields.Char(string='Asuransi', required=True)