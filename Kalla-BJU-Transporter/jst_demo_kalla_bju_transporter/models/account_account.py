from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = 'account.account'

    is_for_driver_remaining_bop = fields.Boolean(
        string='Akun untuk Sisa BOP Driver',
        help='Tandai akun ini sebagai akun untuk sisa BOP driver yang dikembalikan'
    )