from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _name = 'res.config.settings'
    _inherit = ['res.config.settings', 'portfolio.view.mixin']

    enable_cogs_journal_items = fields.Boolean(
        string='Enable COGS Journal Items Generation',
        config_parameter='account.enable_cogs_journal_items',
        help='Enable automatic generation of COGS journal items on invoice save'
    )

    cogs_income_account_id = fields.Many2one(
        'account.account',
        string='COGS Income Account',
        config_parameter='account.cogs_income_account_id',
        help='Account for COGS income entries (Credit side)'
    )

    cogs_expense_account_id = fields.Many2one(
        'account.account',
        string='COGS Expense Account',
        config_parameter='account.cogs_expense_account_id',
        help='Account for COGS expense entries (Debit side)'
    )
