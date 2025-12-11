from odoo import models, api, fields, _

class MiddlewareResponseRequestLog(models.Model):
    _name = 'middleware.response.request.log'

    res_id = fields.Integer()
    name = fields.Char()
    res_model = fields.Selection([
        ('account.move', 'Journal Entry'),
        ('res.partner', 'Partner'),
    ])
    sync_status_code = fields.Integer()
    sync_message = fields.Char()
    payload_sent = fields.Text()
    portfolio = fields.Selection([
        ('frozen', 'Frozen'),
        ('transporter', 'Transporter/Trucking'),
        ('vli', 'VLI'),
    ])
    description = fields.Char()

