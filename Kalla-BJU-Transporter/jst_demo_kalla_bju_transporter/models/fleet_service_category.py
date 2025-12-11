# -*- coding: utf-8 -*-

from odoo import fields, models, api


class FleetServiceCategory(models.Model):
    _name = 'fleet.service.category'
    _description = 'This model is used to categorize the service type'
    _rec_name = 'service_category'

    service_category = fields.Char(string='Category Service', required=True)
