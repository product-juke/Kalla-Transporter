from odoo import fields, models

class mart_revenue(models.Model):
    _name = 'mart.revenue'
    _description = 'Mart Revenue'

    delivery_start_date= fields.Datetime()
    plate_no = fields.Char()
    do_no = fields.Char()
    driver = fields.Char()
    type = fields.Char()
    category = fields.Char()
    customer = fields.Char()
    revenue = fields.Float()
    bop = fields.Float()