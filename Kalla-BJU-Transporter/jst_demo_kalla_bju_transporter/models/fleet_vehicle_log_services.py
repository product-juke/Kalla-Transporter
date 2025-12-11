import requests
import json
from odoo import fields, models, api
from odoo.exceptions import UserError
import warnings

warnings.warn = lambda *args, **kwargs: None
from datetime import timedelta, date
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    no_afs = fields.Char(string='No AFS')
    no_wo = fields.Char(string='No WO')
    jenis_order = fields.Selection([
        ('afs', 'AFS'),
        ('wo', 'WO')
    ], string='Jenis Order', required=True, )
    kode_part = fields.Char(string='Kode Part')
    keluhan = fields.Char(string='Keluhan')
    license_plat = fields.Char(related='vehicle_id.license_plate', string='No Polisi', store=True)
    product_category_id = fields.Many2one(
        'product.category',
        related='vehicle_id.product_category_id',
        store=True,
        string="Business Category"
    )

    def _default_company_code(self):
        company = self.env.company
        return str(company.company_code).lower() if company and company.company_code else False

    branch = fields.Selection(related='vehicle_id.branch', string='Branch', store=True, default=_default_company_code)
    detail_type = fields.Char(related='vehicle_id.detail_type', string='Type', store=True)
    category = fields.Selection(
        related='service_type_id.category',
        string="Category Service", required=True
    )
    qty = fields.Integer(string='Quantity')
    total = fields.Float(string='Cost Total', compute='_compute_total_price')
    cost_category = fields.Selection([
        ('ban', 'Ban'), ('elektrikal', 'Elektrikal'),
        ('jasa', 'Jasa'), ('material', 'Material'),
        ('part', 'Part'), ('pelumas', 'Pelumas'), ('sublet', 'Sublet')
    ], string='Cost Category', required=True, help='Choose whether the Cost Category, vehicle services or both')
    date_in = fields.Date(string='Date In')
    periode = fields.Char(string='Periode', compute='_compute_month_name', store=True)

    @api.onchange('state')
    def on_change_service_state(self):
        for rec in self:
            if rec.state == 'done':
                rec.vehicle_id.vehicle_status = 'ready'

                ready_for_use_status = self.env['fleet.vehicle.status'].search([
                    '|',
                    ('name_description', '=', 'Ready for Use'),
                    ('name_description', '=', 'Ready For Use')
                ], limit=1)
                rec.vehicle_id.last_status_description_id = ready_for_use_status.id
                rec.vehicle_id.maintenance_date = True

    @api.depends('date_in')
    def _compute_month_name(self):
        for record in self:
            if record.date_in:
                record.periode = record.date_in.strftime('%B')
            else:
                record.periode = ''

    @api.depends('qty')
    def _compute_total_price(self):
        for line in self:
            line.total = line.qty * line.amount

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        # Process each created record for vehicle status updates
        today = date.today()

        for record in res:
            date_in_val = record.date_in
            vehicle = record.vehicle_id

            # Process status updates similar to load method
            if vehicle and date_in_val:
                print(f"Processing record - DATE IN: {date_in_val}, VEHICLE: {vehicle.name}")

                # Find or create the 'Breakdown' status description
                breakdown_status = self.env['fleet.vehicle.status'].search([
                    ('name_description', '=', 'Breakdown')
                ], limit=1)

                # Check if date_in is today and update vehicle status
                if str(date_in_val) == str(today):
                    try:
                        # Update vehicle status to 'not_ready'
                        vehicle.write({
                            'vehicle_status': 'not_ready',
                            'maintenance_date': False,
                        })

                        if not breakdown_status:
                            breakdown_status = self.env['fleet.vehicle.status'].create({
                                'name_description': 'Breakdown'
                            })

                        _logger.info(f"Vehicle {vehicle.name} status updated to 'not_ready' with breakdown log")

                    except Exception as e:
                        _logger.error(f"Error updating vehicle status for {vehicle.name}: {str(e)}")

                # Create status log entry
                if breakdown_status:
                    existing_log = self.env['fleet.vehicle.status.log'].search([
                        ('date', '=', date_in_val),
                        ('last_status_description_id', '=', breakdown_status.id),
                        ('vehicle_id', '=', vehicle.id)
                    ])
                    if not existing_log:
                        self.env['fleet.vehicle.status.log'].create({
                            'date': date_in_val,
                            'vehicle_status': 'not_ready',
                            'last_status_description_id': breakdown_status.id,
                            'vehicle_id': vehicle.id
                        })

        return res

    def load(self, fields, data):
        """Get values during import"""

        # Find column indexes
        date_in_index = None
        vehicle_name_index = None

        for field_name in ['date_in', 'DATE IN', 'Date In']:
            if field_name in fields:
                date_in_index = fields.index(field_name)
                break

        for field_name in ['vehicle_id', 'VEHICLE']:
            if field_name in fields:
                vehicle_name_index = fields.index(field_name)
                break

        # Extract values and process status updates
        # Fix: Use date.today() instead of fields.Date.today()
        today = date.today()

        for row_index, row in enumerate(data):
            date_in_val = None
            vehicle_name_val = None

            if date_in_index is not None and len(row) > date_in_index and row[date_in_index]:
                date_in_val = row[date_in_index]
                print(f"Row {row_index + 1} DATE IN: {date_in_val}")

            if vehicle_name_index is not None and len(row) > vehicle_name_index and row[vehicle_name_index]:
                vehicle_name_val = row[vehicle_name_index]
                print(f"Row {row_index + 1} VEHICLE: {vehicle_name_val}")

                # Find or create the 'Breakdown' status description
                breakdown_status = self.env['fleet.vehicle.status'].search([
                    ('name_description', '=', 'Breakdown')
                ], limit=1)

                # Find the vehicle
                vehicle = self.env['fleet.vehicle'].search([
                    ('name', '=', vehicle_name_val),
                ], limit=1)

                # Check if date_in is today and update vehicle status
                if vehicle and date_in_val and str(date_in_val) == str(today):
                    try:
                        # Update vehicle status to 'not_ready'
                        vehicle.write({
                            'vehicle_status': 'not_ready',
                            'maintenance_date': False,
                        })

                        if not breakdown_status:
                            breakdown_status = self.env['fleet.vehicle.status'].create({
                                'name_description': 'Breakdown'
                            })

                        _logger.info(f"Vehicle {vehicle_name_val} status updated to 'not_ready' with breakdown log")

                    except Exception as e:
                        _logger.error(f"Error updating vehicle status for {vehicle_name_val}: {str(e)}")

                # Create status log entry
                if breakdown_status:
                    existing_log = self.env['fleet.vehicle.status.log'].search([
                        ('date', '=', date_in_val),
                        ('last_status_description_id', '=', breakdown_status.id),
                    ])
                    if not existing_log:
                        self.env['fleet.vehicle.status.log'].create({
                            'date': date_in_val,
                            'vehicle_status': 'not_ready',
                            'last_status_description_id': breakdown_status.id,
                            'vehicle_id': vehicle.id
                        })

        return super().load(fields, data)