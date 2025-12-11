from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _name = 'res.config.settings'
    _inherit = ['res.config.settings', 'portfolio.view.mixin']

    url_bju = fields.Char(string='URL', config_parameter='jst_integration_bju.url_bju')
    port = fields.Char(string='Port', config_parameter='jst_integration_bju.port')
    Authorization = fields.Char(string='Authorization', config_parameter='jst_integration_bju.Authorization')
    UserAgent = fields.Char(string='User-Agent', config_parameter='jst_integration_bju.UserAgent')
    clientId = fields.Char(string='clientId', config_parameter='jst_integration_bju.clientId')
    clientIdReceipt = fields.Char(string='clientId', config_parameter='jst_integration_bju.clientIdReceipt')
    sha256Token = fields.Char(string='SHA-256 Token', config_parameter='jst_integration_bju.sha256Token')
    writeoff_account_id = fields.Many2one('account.account', string='Post Difference In', config_parameter='jst_integration_bju.writeoff_account_id')
    writeoff_label = fields.Char(string='Label', config_parameter='jst_integration_bju.writeoff_label')
    sync_customer_to_oracle = fields.Boolean(string='Sync to Oracle', config_parameter='jst_integration_bju.sync_customer_to_oracle')
    sync_ar_to_oracle = fields.Boolean(string='Sync to Oracle', config_parameter='jst_integration_bju.sync_ar_to_oracle')
    sync_ap_to_oracle = fields.Boolean(string='Sync to Oracle', config_parameter='jst_integration_bju.sync_ap_to_oracle')
    use_queue_customer = fields.Boolean(string='Use Queue', config_parameter='jst_integration_bju.use_queue_customer')
    use_queue_ar = fields.Boolean(string='Use Queue', config_parameter='jst_integration_bju.use_queue_ar')
    use_queue_ap = fields.Boolean(string='Use Queue', config_parameter='jst_integration_bju.use_queue_ap')
