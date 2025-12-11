from odoo import models, fields, api, _

class OracleSyncLog(models.Model):
    _name = 'oracle.sync.log'
    _description = 'Oracle Synchronization Log'

    flag = fields.Selection([
        ('failed', 'Failed'),
        ('success', 'Success'),
    ])
    related_id = fields.Integer(
        string="Related ID in Model"
    )
    res_model = fields.Char()
    status_code = fields.Integer()
    message = fields.Text()