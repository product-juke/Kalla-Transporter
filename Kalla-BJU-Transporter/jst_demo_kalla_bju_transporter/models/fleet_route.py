# -*- coding: utf-8 -*-
from odoo import fields, models, api
from pkg_resources import require


class FleetRoute(models.Model):
    _name = 'fleet.route'
    _rec_name = 'name'
    _description = 'Route'

    name = fields.Char()
    fleet_category_id = fields.Many2one('fleet.vehicle.model.category', required=True)
    autoid = fields.Integer(string='Auto Id')
    code = fields.Char(string='Code', required=True)
    origin_id = fields.Many2one('master.origin', string='Origin', required=True)
    destination_id = fields.Many2one('master.destination', string='Destination', required=True)
    rate = fields.Monetary(currency_field='currency_id', required=True)
    company_id = fields.Many2one('res.company', required=True)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)
    sla = fields.Integer('SLA (days)', required=True    )
    #
    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('origin_id') and vals.get('destination_id'):
    #             vals['name'] = '%s - %s' % (vals['origin_id'], vals['destination_id'])
    #     return super().create(vals_list)
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('origin_id') and vals.get('destination_id') and vals.get('fleet_category_id'):
                origin = self.env['master.origin'].browse(vals['origin_id'])
                destination = self.env['master.destination'].browse(vals['destination_id'])
                fleet_category = self.env['fleet.vehicle.model.category'].browse(vals['fleet_category_id'])
                vals['name'] = f"{fleet_category.name} - {origin.name} - {destination.name}"
        return super().create(vals_list)