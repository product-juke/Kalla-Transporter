# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models, api, _


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    fleet_vehicle_id = fields.Many2one('fleet.vehicle')

