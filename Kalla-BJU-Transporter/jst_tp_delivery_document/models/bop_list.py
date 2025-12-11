# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetDo(models.Model):
    _inherit = 'bop.line'
    _description = 'fleet_do'

    status_delivery = fields.Selection(string='Status Delivery', selection=[('draft', 'Draft'), ('on_going', 'On Going'),
                                                  ('on_return', 'On Return'), ('good_receive', 'Good Receipt')],
                                       default='draft', related='fleet_do_id.status_delivery', store=True)


