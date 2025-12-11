# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import json


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    vehicle_ids = fields.Many2many(comodel_name='product.product')
    muatan_unit = fields.Char()
    route = fields.Many2one('fleet.route')
    rate = fields.Monetary(currency_field='company_currency', related='route.rate')
    harga_jual = fields.Monetary(currency_field='company_currency', compute='compute_harga_jual', store=True)
    is_sewa_vendor = fields.Boolean('Sewa Vendor?')
    biaya_sewa_vendor_pihak_ketiga = fields.Monetary('Biaya Sewa Vendor (Pihak Ketiga)', currency_field='company_currency')
    # biaya_operasional = fields.Monetary(currency_field='company_currency', compute='compute_biaya_operasional', store=True)
    total_profit = fields.Monetary(currency_field='company_currency', compute='compute_total_profit', store=True)
    line_ids = fields.One2many(comodel_name='costing.sales', inverse_name='crm_id')
    expected_revenue = fields.Monetary('Expected Revenue', currency_field='company_currency', tracking=True, compute="compute_exp_rev")

    @api.depends('line_ids.nilai_revenue')
    def compute_exp_rev(self):
        for rec in self:
            rev = 0
            rec.expected_revenue = 0
            for line in rec.line_ids:
                if line.nilai_revenue:
                    rev += line.nilai_revenue
            rec.expected_revenue = rev

    @api.depends('expected_revenue')
    def compute_harga_jual(self):
        for rec in self:
            rec.harga_jual = 0
            if rec.expected_revenue:
                if rec.expected_revenue < sum(rec.line_ids.mapped('nilai_hpp')):
                    raise ValidationError(_('Total Harga Jual cannot less than HPP!'))
                rec.harga_jual = rec.expected_revenue

    # @api.depends('vehicle_ids', 'vehicle_ids.vehicle_id.x_studio_total_hpp')
    # def compute_biaya_operasional(self):
    #     for rec in self:
    #         rec.biaya_operasional = 0
    #         if rec.vehicle_ids:
    #             rec.biaya_operasional = sum(rec.line_ids.mapped('nilai_hpp'))

    def action_new_quotation(self):
        res = super(CrmLead, self).action_new_quotation()
        order_line = []
        for line in self.line_ids:
            order_line.append(
                (0, 0, {'product_id': line.vehicle_id.id}),
            )
        res['context']['default_order_line'] = order_line
        return res

    @api.onchange('is_sewa_vendor')
    def onchange_is_sewa_vendor(self):
        self.biaya_operasional = False
        self.biaya_sewa_vendor_pihak_ketiga = False

    @api.depends('harga_jual', 'biaya_sewa_vendor_pihak_ketiga')
    def compute_total_profit(self):
        for rec in self:
            rec.total_profit = 0.0
            if rec.is_sewa_vendor:
                rec.total_profit = rec.harga_jual - rec.biaya_sewa_vendor_pihak_ketiga
            else:
                rec.total_profit = rec.harga_jual - rec.biaya_operasional

    @api.depends(lambda self: ['stage_id', 'team_id'] + self._pls_get_safe_fields())
    def _compute_probabilities(self):
        res = super(CrmLead, self)._compute_probabilities()
        for rec in self:
            if rec.stage_id.name == 'New':
                rec.probability = 10
            elif rec.stage_id.name == 'Won':
                rec.probability = 100
        return res

    def create_contract(self):
        contract = self.env['create.contract']
        contract_line = []
        for rec in self:
            for line in rec.line_ids:
                contract_line.append((0, 0, {
                    # 'name': line.vehicle_id.name,
                    # 'vehicle_id': line.vehicle_id.id,
                    'origin_id': line.origin.id,
                    'destination_id': line.destination.id,
                    'price': line.nilai_revenue,
                }))
            new_contract = contract.create({
                'partner_id': rec.partner_id.id,
                'name': rec.partner_id.name + ' Contract' if rec.partner_id.name else 'Contract',
                'company_id': rec.company_id.id,
                'email': rec.email_from,
                'phone': rec.phone,
                'responsible_id': rec.user_id.id,
                'crm_id': rec.id,
                'line_ids': contract_line
            })

            return {
                'type': 'ir.actions.act_window',
                'name': 'Open Record',
                'res_model': 'create.contract',
                'view_mode': 'form',
                'res_id': new_contract.id,
                'target': 'current',
            }

class CostingSales(models.Model):
    _name = 'costing.sales'

    crm_id = fields.Many2one('crm.lead')
    category_id = fields.Many2one(comodel_name='fleet.vehicle.model.category')
    # vehicle_id = fields.Many2one(comodel_name='product.product', name='Fleet')
    # jenis_muatan = fields.Selection([('dry', 'Dry'), ('cold', 'Cold')], 'Jenis Muatan')
    # asset_vendor = fields.Selection(name='Asset/Vendor')
    # origin = fields.Many2one('x_master_origin', 'Origin')
    # destination = fields.Many2one('x_master_destination', 'Destination')
    origin_id = fields.Many2one('master.origin', 'Origin')
    destination_id = fields.Many2one('master.destination', 'Destination')
    nilai_hpp = fields.Float('HPP', compute='compute_biaya_operasional')
    nilai_revenue = fields.Float('Expected Revenue')
    nilai_profit = fields.Float('Profit', compute='compute_profit')
    state = fields.Selection([('no_good', 'Not Good'), ('good', 'Good')], 'Status', compute='compute_state')
    # vehicle_domain = fields.Char(compute='compute_vehicle_domain')

    # @api.depends('category_id')
    # def compute_biaya_operasional(self):
    #     for rec in self:
    #         rec.nilai_hpp = 0
    #         if rec.category_id:
    #             hpp = rec.env['fleet.vehicle'].search([('category_id', '=', rec.category_id.id)]).mapped('x_studio_total_hpp')
    #             rec.nilai_hpp = hpp[0] if hpp else 0

    @api.depends('nilai_hpp', 'nilai_revenue')
    def compute_profit(self):
        for rec in self:
            rec.nilai_profit = 0
            if rec.nilai_hpp and rec.nilai_revenue:
                rec.nilai_profit = rec.nilai_revenue - rec.nilai_hpp

    @api.depends('nilai_profit')
    def compute_state(self):
        for rec in self:
            rec.state = 'no_good'
            if rec.nilai_profit < 0:
                rec.state = 'no_good'
            else:
                rec.state = 'good'

    # @api.depends('category_id')
    # def compute_vehicle_domain(self):
    #     for rec in self:
    #         product = self.env['fleet.vehicle'].search([
    #             ('category_id', '=', rec.category_id.id),
    #         ])
    #         rec.vehicle_domain = json.dumps(
    #             [('vehicle_id', 'in', product.mapped('id'))]
    #         )