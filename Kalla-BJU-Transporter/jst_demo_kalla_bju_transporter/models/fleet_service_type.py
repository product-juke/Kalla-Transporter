# -*- coding: utf-8 -*-
from datetime import timedelta, date
from email.policy import default
import requests
import json
from odoo import fields, models, api
from odoo.exceptions import UserError
import warnings
warnings.warn = lambda *args, **kwargs: None


class FleetServiceType(models.Model):
    _inherit = 'fleet.service.type'

    category = fields.Selection([
        ('general_repair', 'General Repair'),
        ('reguler_check', 'Reguler Check'),
        ('tire', 'TIRE'), ('sublet', 'Sublet')
    ], 'Category', required=True, help='Choose whether the service refer to contracts, vehicle services or both')

    # Get service category from
    category_service_id = fields.Many2one(
        'fleet.service.category',
        string='Category Service',
        help="Select the category of the service type",
    )
