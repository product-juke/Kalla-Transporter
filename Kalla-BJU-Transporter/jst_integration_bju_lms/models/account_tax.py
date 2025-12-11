from odoo import fields, models, _
import json, datetime, http.client
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = ['account.tax', 'portfolio.view.mixin']

    group = fields.Selection([
        ('ppn', 'PPN'),
        ('pph', 'PPH'),
    ], string="Group", default="ppn")
    oracle_tax_name = fields.Char(
        string="Oracle Tax Name",
        help="Pada Transporter/VLI/Trucking, field ini digunakan sebagai nilai pada key TaxClassification di payload saat pengiriman data ke Middleware, dan bersifat required. Sementara itu, pada Frozen, field ini tidak bersifat required serta tidak disertakan dalam payload saat pengiriman data ke Middleware.",
    )
