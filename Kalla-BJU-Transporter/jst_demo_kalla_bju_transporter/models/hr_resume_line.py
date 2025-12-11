from odoo import fields, models, api

class HrResumeLine(models.Model):
    _inherit = 'hr.resume.line'

    position = fields.Char(string='Positions')
    resign_description = fields.Char(string='Resign Description')
    training_plan = fields.Char(string='Training Plan')
    file_certificate_training = fields.Binary("Upload File Certificate Training")
    file_certificate_name = fields.Char("Nama File Certificate")
    training_plan_date = fields.Date(string='Training Plan Date')
    recruitment_type = fields.Selection([('bju', 'BJU Recruitment'),
                                       ('outsource', 'Out Source'),('driver', 'Driver Recomended')], string='Status Delivery Document', default=False)