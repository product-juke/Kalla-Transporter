# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DriverSelectionWizard(models.TransientModel):
    _name = 'driver.selection.wizard'
    _description = 'Select Driver Wizard'

    # context document (like fleet.do)
    fleet_do_id = fields.Many2one('fleet.do', required=True)

    # selected result + display
    selected_driver_id = fields.Many2one('res.partner', readonly=True)
    selected_driver_display = fields.Char(compute='_compute_selected_driver_display', readonly=True)

    # optional filters (kept invisible for now to match your vehicle wizard)
    filter_company_id = fields.Many2one('res.company')
    filter_status = fields.Selection([
        ('ready', 'Ready'),
        ('on_duty', 'On Duty'),
        ('off', 'Off'),
    ])

    # candidate list shown in the wizard (M2M to res.partner)
    driver_ids = fields.Many2many(
        'res.partner',
        string='Drivers',
        compute='_compute_driver_ids',
        compute_sudo=True,
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'fleet.do':
            res['fleet_do_id'] = self.env.context.get('active_id')
        return res

    def _eligible_domain(self):
        """Base domain: drivers that are Ready."""
        dom = [
            ('is_driver', '=', True),
            ('availability', '=', 'Ready'),
        ]
        # multi-company safety (optional)
        company_id = self.filter_company_id.id if self.filter_company_id else (
            self.fleet_do_id.company_id.id if self.fleet_do_id else False
        )
        if company_id:
            dom.append(('company_id', 'in', [False, company_id]))
        return dom

    @api.depends('filter_company_id', 'fleet_do_id')
    def _compute_driver_ids(self):
        Partner = self.env['res.partner'].sudo()
        for wiz in self:
            drivers = Partner.search(wiz._eligible_domain(), order='write_date asc, id asc', limit=500)
            wiz.driver_ids = [(6, 0, drivers.ids)]

    @api.depends('selected_driver_id')
    def _compute_selected_driver_display(self):
        for wiz in self:
            wiz.selected_driver_display = wiz.selected_driver_id.display_name if wiz.selected_driver_id else False


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_select_this_driver(self):
        self.ensure_one()
        wiz_id = self.env.context.get('wizard_id')
        if not wiz_id and self.env.context.get('active_model') == 'driver.selection.wizard':
            # sometimes the client keeps the wizard as active
            wiz_id = self.env.context.get('active_id')

        wiz = self.env['driver.selection.wizard'].browse(wiz_id)
        if not wiz.exists():
            raise UserError(_("Wizard not found or expired."))

        if not (self.is_driver and self.availability == 'Ready'):
            raise UserError(_("This driver is not currently Ready."))

        if wiz.fleet_do_id and 'driver_id' in wiz.fleet_do_id._fields:
            wiz.fleet_do_id.sudo().write({'driver_id': self.id})
        wiz.sudo().write({'selected_driver_id': self.id})

        return {'type': 'ir.actions.act_window_close'}
