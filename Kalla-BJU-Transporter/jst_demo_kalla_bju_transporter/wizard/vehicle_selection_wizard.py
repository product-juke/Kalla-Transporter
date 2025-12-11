from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VehicleSelectionWizard(models.TransientModel):
    _name = 'vehicle.selection.wizard'
    _description = 'Vehicle Selection Wizard'

    fleet_do_id = fields.Many2one('fleet.do', string='Fleet DO', required=True)
    selected_vehicle_id = fields.Many2one('fleet.vehicle', string='Selected Vehicle')
    selected_vehicle_display = fields.Char(string='Selected Vehicle', compute='_compute_selected_vehicle_display')

    # Fields for domain filtering
    category_id = fields.Many2one('fleet.vehicle.model.category', string='Category')
    tonase_line = fields.Float(string='Tonase Required')
    kubikasi_line = fields.Float(string='Kubikasi Required')

    # Filter fields
    filter_category_id = fields.Many2one('fleet.vehicle.model.category', string='Category Filter')
    filter_status = fields.Selection([
        ('ready', 'Ready'),
        ('on_going', 'On Going'),
        ('not_ready', 'Not Ready'),
    ], string='Status Filter')

    # Available vehicles
    vehicle_ids = fields.Many2many('fleet.vehicle', string='Available Vehicles', compute='_compute_available_vehicles')

    @api.depends('category_id', 'tonase_line', 'kubikasi_line')
    def _compute_available_vehicles(self):
        for record in self:
            fleet_do_id = self.env.context.get('active_id')
            fleet_do = self.env['fleet.do'].search([
                ('id', '=', fleet_do_id)
            ])
            
            if not fleet_do:
                raise UserError(_("DO tidak ditemukan"))
            
            category_id = self.env.context.get('category_id')
            domain = [
                ('category_id', '=', category_id),
                ('vehicle_status', '=', 'ready'),
                ('last_status_description_id.name_description', '=', 'Ready for Use'),
                ('driver_id.availability', '=', 'Ready'),
            ] if not fleet_do.category_id.is_shipment else [
                ('category_id', '=', category_id),
                ('vehicle_status', '=', 'ready'),
                ('last_status_description_id.name_description', '=', 'Ready for Use'),
            ]

            if category_id and not fleet_do.category_id.is_shipment:
                domain.extend([
                    ('category_id.min_tonase', '<=', fleet_do.tonase_line),
                    ('category_id.max_tonase', '>=', fleet_do.tonase_line),
                    ('category_id.min_kubikasi', '<=', fleet_do.kubikasi_line),
                    ('category_id.max_kubikasi', '>=', fleet_do.kubikasi_line),
                ])
            else:
                domain.extend([
                    ('category_id.max_unit', '>=', sum(fleet_do.po_line_ids.filtered(
                        lambda line: not line.is_line).mapped('product_qty'))),
                ])

            print('domain => ', domain)

            vehicles = self.env['fleet.vehicle'].search(
                domain,
                order='asset_type asc, date_sort_helper asc, write_date asc'
            )
            record.vehicle_ids = [(6, 0, vehicles.ids)]

    @api.depends('selected_vehicle_id')
    def _compute_selected_vehicle_display(self):
        for record in self:
            if record.selected_vehicle_id:
                vehicle = record.selected_vehicle_id
                record.selected_vehicle_display = f"{vehicle.license_plate} - {vehicle.name} ({vehicle.no_lambung})"
            else:
                record.selected_vehicle_display = ""

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        print("self.env.context.get('active_id')", self.env.context.get('active_id'))

        fleet_do_id = self.env.context.get('active_id')
        category_id = self.env.context.get('category_id')
        tonase_line = self.env.context.get('tonase_line')
        kubikasi_line = self.env.context.get('kubikasi_line')
        res['fleet_do_id'] = fleet_do_id

        # Get data from fleet.do to populate domain fields
        fleet_do = self.env['fleet.do'].browse(fleet_do_id)
        if category_id and tonase_line and kubikasi_line:
            # Adjust these field names based on your fleet.do model
            res['category_id'] = category_id if category_id else False
            res['tonase_line'] = tonase_line if tonase_line else 0.0
            res['kubikasi_line'] = kubikasi_line if kubikasi_line else 0.0

        return res

    def action_select_this_vehicle(self):
        """Action called from tree view button to select a vehicle"""
        # This method should be called with vehicle_id in context
        vehicle_id = self.env.context.get('vehicle_id')

        if not vehicle_id:
            # Try to get from active_id if called directly on vehicle
            vehicle_id = self.env.context.get('active_id')
            # Check if active_id is actually a vehicle
            if vehicle_id and self.env.context.get('active_model') == 'fleet.vehicle':
                pass  # vehicle_id is correct
            else:
                vehicle_id = None

        if vehicle_id:
            vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
            if vehicle.exists():
                self.selected_vehicle_id = vehicle_id

                # Update the fleet DO
                if self.fleet_do_id:
                    self.fleet_do_id.vehicle_id = vehicle_id
                    # Also update driver if vehicle has one
                    if vehicle.driver_id:
                        self.fleet_do_id.driver_id = vehicle.driver_id.id

        # Return action to refresh/close the wizard
        return {
            'type': 'ir.actions.act_window_close'
        }

    def action_confirm_selection(self):
        """Confirm the vehicle selection and close wizard"""
        if not self.selected_vehicle_id:
            raise UserError(_("Please select a vehicle first."))

        if not self.fleet_do_id:
            raise UserError(_("Fleet DO not found."))

        # Update the fleet.do record with selected vehicle
        self.fleet_do_id.write({
            'vehicle_id': self.selected_vehicle_id.id,
            'driver_id': self.selected_vehicle_id.driver_id.id if self.selected_vehicle_id.driver_id else False,
        })

        # Show success message
        message = _("Vehicle %s has been selected for DO %s") % (
            self.selected_vehicle_id.license_plate,
            self.fleet_do_id.name
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vehicle Selected'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_vehicle_list(self):
        """Open a list view of available vehicles with select buttons"""
        return {
            'name': _('Select Vehicle'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle',
            'view_mode': 'tree',
            'target': 'new',
            'domain': [
                ('category_id', '=', self.category_id.id),
                ('vehicle_status', '=', 'ready'),
                ('driver_id.availability', '=', 'Ready'),
                ('category_id.min_tonase', '<=', self.tonase_line),
                ('category_id.max_tonase', '>=', self.tonase_line),
                ('category_id.min_kubikasi', '<=', self.kubikasi_line),
                ('category_id.max_kubikasi', '>=', self.kubikasi_line),
            ],
            'context': {
                'active_model': 'vehicle.selection.wizard',
                'active_id': self.id,
                'wizard_id': self.id,
            }
        }

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    date_sort_helper = fields.Char(compute='_compute_date_sort_helper', store=True)

    @api.depends('date_of_status_ready')
    def _compute_date_sort_helper(self):
        for record in self:
            if record.date_of_status_ready:
                # Untuk nilai yang ada, gunakan format yang akan diurutkan setelah '0'
                record.date_sort_helper = '1' + str(record.date_of_status_ready)
            else:
                # Untuk NULL, gunakan '0' agar muncul di atas
                record.date_sort_helper = '0'

    def action_select_this_vehicle(self):
        """Action to select this vehicle in wizard context"""
        # Get the active wizard from context (if called from wizard view)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        wizard_id = self.env.context.get('wizard_id')

        # Check if we're in wizard context
        if active_model == 'vehicle.selection.wizard' and active_id:
            wizard = self.env['vehicle.selection.wizard'].browse(active_id)
            if wizard.exists():
                # Set selected vehicle in wizard
                wizard.selected_vehicle_id = self.id

                # Set vehicle to fleet DO
                if wizard.fleet_do_id:
                    wizard.fleet_do_id.vehicle_id = self.id
                    # Also update driver if vehicle has one
                    if self.driver_id:
                        wizard.fleet_do_id.driver_id = self.driver_id.id

                # Close the popup and show notification
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Vehicle Selected'),
                        'message': _('Vehicle %s has been selected successfully!') % self.license_plate,
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.act_window_close'
                        }
                    }
                }

        # Alternative approach using wizard_id from context
        if wizard_id:
            wizard = self.env['vehicle.selection.wizard'].browse(wizard_id)
            if wizard.exists():
                # Set selected vehicle
                wizard.selected_vehicle_id = self.id

                # Set vehicle to fleet DO
                if wizard.fleet_do_id:
                    wizard.fleet_do_id.vehicle_id = self.id
                    if self.driver_id:
                        wizard.fleet_do_id.driver_id = self.driver_id.id

                # Close popup with notification
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Vehicle Selected'),
                        'message': _('Vehicle %s has been selected for DO %s') % (
                            self.license_plate,
                            wizard.fleet_do_id.name if wizard.fleet_do_id else 'Unknown'
                        ),
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.act_window_close'
                        }
                    }
                }

        # Alternative approach: find active wizard by searching recent records
        wizard = self.env['vehicle.selection.wizard'].search([
            ('create_uid', '=', self.env.user.id)
        ], order='create_date desc', limit=1)

        if wizard:
            # Set selected vehicle
            wizard.selected_vehicle_id = self.id

            # Set vehicle to fleet DO
            if wizard.fleet_do_id:
                wizard.fleet_do_id.vehicle_id = self.id
                if self.driver_id:
                    wizard.fleet_do_id.driver_id = self.driver_id.id

            # Close popup and show success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Vehicle Selected'),
                    'message': _('Vehicle %s has been selected for DO %s') % (
                        self.license_plate,
                        wizard.fleet_do_id.name if wizard.fleet_do_id else 'Unknown'
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window_close'
                    }
                }
            }

        # Fallback: show error message and close
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Error'),
                'message': _('No active vehicle selection wizard found.'),
                'type': 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }

class FleetDO(models.Model):
    _inherit = 'fleet.do'  # Adjust this to your actual model name

    def action_reset_current_fleet(self):
        self.ensure_one()
        self.vehicle_id = False
        self.driver_id = False

    def action_reset_current_driver(self):
        self.ensure_one()
        self.driver_id = False

    def action_select_vehicle_wizard(self):
        """Open vehicle selection wizard"""
        # Create wizard record first
        wizard = self.env['vehicle.selection.wizard'].create({
            'fleet_do_id': self.id,
        })

        return {
            'name': _('Select Vehicle'),
            'type': 'ir.actions.act_window',
            'res_model': 'vehicle.selection.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }