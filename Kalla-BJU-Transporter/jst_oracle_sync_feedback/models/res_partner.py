from odoo import models, fields, api, _

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'portfolio.view.mixin']

    is_failed_sync_to_oracle = fields.Boolean(
        help="Mendapatkan informasi apakah data ini gagal masuk ke oracle atau tidak",
        default=False
    )
    oracle_sync_log_status_code = fields.Char('Status Code', copy=False, tracking=True)
    oracle_sync_log_message = fields.Char('Message', copy=False, tracking=True)
    oracle_sync_log_date = fields.Datetime('Sync Date', copy=False, tracking=True)
