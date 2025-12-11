from odoo import fields, models, api, _

class TrxVehicleNonUtilization(models.Model):
    _name = 'trx.vehicle.non.utilization'
    _description = 'Vehicle Non Utilization Transaction'

    date = fields.Date()
    plate_no = fields.Char()

    status_plan = fields.Char(
        string='Status Plan'
    )

    status_actual = fields.Char(
        string='Status Actual'
    )

    vehicle_name = fields.Char()
    do_no_lms = fields.Char()
    do_no_tms = fields.Char()
    do_id_lms = fields.Integer(string="ID DO (Odoo LMS)")
    driver = fields.Char()
    product = fields.Char()
    category = fields.Char()
    so_no = fields.Char()
    customer = fields.Char()
    # revenue = fields.Float()
    invoice_no = fields.Char()
    # bop = fields.Float()
    branch_project = fields.Char()
    vehicle_status_log_id = fields.Integer()