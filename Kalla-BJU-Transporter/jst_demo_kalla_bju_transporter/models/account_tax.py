from odoo import fields, models, _
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = 'account.tax'

    use_dpp_nilai_lain = fields.Boolean('DPP Nilai Lain')
