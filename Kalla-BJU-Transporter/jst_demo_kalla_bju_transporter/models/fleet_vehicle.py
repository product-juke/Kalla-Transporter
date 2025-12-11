# -*- coding: utf-8 -*-
from email.policy import default
import requests
import json
from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
import warnings ; warnings.warn = lambda *args,**kwargs: None
from datetime import timedelta, date, datetime
import logging

_logger = logging.getLogger(__name__)

BRANCH = [
    ('lmks', "LMKS"),
    ('ljkt', "LJKT"),
    ('vli', "VLI"),
    ('clm', "CLM"),
    ('bpp', "BPP"),
    ('sby1', "SBY1"),
    ('bpp1', "BPP1"),
    ('mks1', "MKS1"),
    ('mks2', "MKS2"),
    ('lwu', "LWU"),
    ('cabo', "CABO"),
]

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    vehicle_name = fields.Char(string='Vehicle Name', store=True, compute='compute_vehicle_name')
    _rec_name = 'vehicle_name'
    vehicle_id = fields.Char('Vehicle ID')
    no_lambung = fields.Char('NO Lambung')
    #current_time = fields.Datetime(string='Current time', compute='_get_current_time')
    # current_time = fields.Date(string='Current Time', default=lambda s: fields.Date.context_today(s), compute='_get_current_time')
    branch = fields.Selection(selection=BRANCH, default=False)
    gps_status = fields.Selection([('installed', 'Installed'),
                                   ('not installed', 'Not Installed')], string='GPS Status', default=False, tracking=True)
    end_of_tax_period = fields.Date('End of Tax Period', tracking=True)
    detail_type = fields.Char('Detail Type', tracking=True)
    engine_sn = fields.Char('Engine Number', tracking=True)
    stnk_expiration_period = fields.Date('STNK Expiration Period', tracking=True)
    vehicle_status = fields.Selection([('ready', 'Ready'),
                                       ('on_going', 'On Going'),
                                       ('on_return', 'On Return'),
                                       ('not_ready', 'Not Ready')], string='Last Status', default=False, tracking=True)
    last_status_description_id = fields.Many2one('fleet.vehicle.status', domain="[('vehicle_status','=',vehicle_status)]", string="Last Status Description", tracking=True)
    radius = fields.Float('Radius (km)', tracking=True)
    geofence = fields.Selection([('loading', 'Area Loading'),
                                 ('checkpoint', 'Area Checkpoint'),
                                 ('unloading', 'Area Unloading')], default=False, tracking=True)
    geofence_checkpoint = fields.Boolean('Geofence Checkpoint')
    maintenance_date = fields.Boolean('Maintenance Date')
    driver_confirmation = fields.Boolean('Driver Confirmation')
    plan_armada_confirmation = fields.Boolean('P2H Confirmation')
    min_tonase = fields.Float('Minimum Tonase', readonly=True, related='category_id.min_tonase')
    max_tonase = fields.Float('Maximum Tonase', readonly=True, related='category_id.max_tonase')
    min_kubikasi = fields.Float('Minimum Kubikasi', readonly=True, related='category_id.min_kubikasi')
    max_kubikasi = fields.Float('Maximum Kubikasi', readonly=True, related='category_id.max_kubikasi')
    max_unit = fields.Float('Maximum Unit', readonly=True, related='category_id.max_unit')
    current_time = fields.Datetime(string='Current Time')
    target_line_ids = fields.One2many(comodel_name='vehicle.target.line', inverse_name='vehicle_id')
    wheels = fields.Integer('Wheels Number')
    jam_kerja_start = fields.Float(string="Mulai Jam Kerja",
                                    digits=(6, 2),  # 9999.99 hours maximum
                                    help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                    )
    jam_kerja_end = fields.Float(string="Selesai Jam Kerja",
                                   digits=(6, 2),  # 9999.99 hours maximum
                                   help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                   )
    jam_tersedia = fields.Float(string="Jam Tersedia",
                                 digits=(6, 2),  # 9999.99 hours maximum
                                 help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                 )
    jam_breakdown = fields.Float(string="Jam Breakdown",
                                      digits=(6, 2),  # 9999.99 hours maximum
                                      help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                      )
    jam_istirahat = fields.Float(string="Jam Istirahat",
                                       digits=(6, 2),  # 9999.99 hours maximum
                                       help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                       )
    jam_hujan = fields.Float(string="Jam Hujan",
                                       digits=(6, 2),  # 9999.99 hours maximum
                                       help="Time spent in hours (e.g., 1.5 = 1 hour 30 minutes)"
                                       )
    product_category_id = fields.Many2one(
        'product.category',
        related='category_id.product_category_id',
        store=True,
        readonly=True,
        string="Business Category"
    )
    is_stnk_expiring = fields.Boolean(string="STNK Akan Kedaluwarsa", compute="_compute_stnk_expiry", store=True)
    due_date = fields.Date(string="SLA", default=lambda self: fields.Date.context_today(self))
    asset_type = fields.Selection([
        ('asset', 'Asset'),
        ('vendor', 'Vendor')
    ], string="Asset Type")
    load_type = fields.Selection([
        ('dry', 'Dry'),
        ('cold', 'Cold')
    ], string="Jenis Muatan")
    vichle_ownership = fields.Many2one(
        'res.partner',
        string='Vichle Ownership',
        domain=[('is_company', '=', True)],
        required=True
    )

    is_end_of_tax_period_exp = fields.Boolean(string="End Of Tax akan Kadarluasa ", compute="_compute_end_of_tax_period_exp", store=True)
    is_stnk_expiration_period_exp = fields.Boolean(string="STNK akan Kadarluasa", compute="_compute_stnk_expiration_period_exp", store=True)
    seats = fields.Integer(string="Seats Number")
    doors = fields.Integer(string="Doors Number")
    model_year = fields.Integer(string="Model Year")
    horsepower = fields.Integer(string="Horsepower")
    power = fields.Float(string="Power")
    co2 = fields.Integer(string="CO2 Emission")
    co2_standard = fields.Char(string="CO2 Standard", size=50)
    vehicle_status_log_ids = fields.One2many(comodel_name='fleet.vehicle.status.log', inverse_name='vehicle_id')
    previous_status_description_id = fields.Many2one('fleet.vehicle.status',
                                                 domain="[('vehicle_status','=',vehicle_status)]",
                                                 string="Last Status Description", tracking=True)
    date_of_status_ready = fields.Date(string="Latest Date of Status Ready")
    customer_id = fields.Many2one('res.partner', 'Dedicated to', domain="[('is_customer','=',True)]")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)
    fix_cost = fields.Monetary('Fix Cost', currency_field='currency_id', store=True)
    forecast_status_ready = fields.Char(string="Forecast Status Ready", readonly=True, default="Ready for Use")
    ewd_ids = fields.One2many(
        'fleet.vehicle.ewd',
        'fleet_vehicle_id',
        string="EWD Records"
    )
    company_portfolio = fields.Char(
        related='company_id.portfolio_id.name',
        store=True,
        string='Company Portfolio'
    )

    @api.constrains('seats', 'doors', 'wheels', 'model_year',
                    'horsepower', 'power', 'co2', 'co2_standard', 'license_plate')
    def _check_field_constraints(self):
        for record in self:
            if record.seats and (record.seats < 0 or record.seats > 99):
                raise ValidationError("Seats Number must be 0 - 99.")
            if record.doors and (record.doors < 0 or record.doors > 99):
                raise ValidationError("Doors Number must be 0 - 99.")
            if record.wheels and (record.wheels < 0 or record.wheels > 99):
                raise ValidationError("Wheels Number must be 0 - 99.")
            if record.model_year and (record.model_year < 0 or record.model_year > 9999):
                raise ValidationError("Model Year must be 0 - 9999.")
            if record.horsepower and (record.horsepower < 0 or record.horsepower > 9999):
                raise ValidationError("Horsepower must be 0 - 9999.")
            if record.power and (record.power < 0 or record.power > 9999):
                raise ValidationError("Power must be 0 - 9999.")
            if record.co2 and (record.co2 < 0 or record.co2 > 9999):
                raise ValidationError("CO2 Emission must be 0 - 9999.")
            if record.co2_standard and len(record.co2_standard) > 50:
                raise ValidationError("CO2 Standard must be max 50 characters.")
            if record.license_plate:
                # Cari vehicle lain dengan license_plate yang sama (kecuali record saat ini)
                duplicate_vehicles = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', record.license_plate),
                    ('id', '!=', record.id)
                ])

                if duplicate_vehicles:
                    raise ValidationError(
                        f"License Plate '{record.license_plate}' sudah digunakan oleh vehicle lain. "
                        # f"Setiap vehicle harus memiliki License Plate yang unik."
                    )

    @api.model
    def _cron_auto_update_vehicle_status(self):
        """
        Method khusus untuk dipanggil oleh cron job
        """
        _logger.info('Auto Update Vehicle Status Started Execution')
        try:
            # Ambil semua kendaraan untuk diproses
            vehicles = self.search([])
            _logger.info(f'Processing {len(vehicles)} vehicles for status update')

            self.update_last_status_vehicle_by_end_of_tax_period()
            self.update_last_status_vehicle_by_stnk_expiration_period()

            _logger.info('Auto Update Vehicle Status Completed Execution')
        except Exception as e:
            _logger.error(f'Error in _cron_auto_update_vehicle_status: {str(e)}')
            raise

    def update_last_status_vehicle_by_end_of_tax_period(self):
        """
        Update vehicle status berdasarkan masa berlaku pajak
        """
        today = fields.Date.today()
        updated_count = 0
        error_count = 0

        _logger.info('Starting update vehicle status by end of tax period')

        # Ambil semua kendaraan jika method dipanggil pada model tanpa recordset
        vehicles = self if self else self.search([])

        for rec in vehicles:
            try:
                if not rec.end_of_tax_period:
                    continue

                is_expr_not_ready = (rec.end_of_tax_period - today).days <= 0

                if is_expr_not_ready:
                    old_status = rec.vehicle_status
                    rec.vehicle_status = "not_ready"

                    status = self.env['fleet.vehicle.status'].search([
                        ('name_description', 'ilike', 'license not')
                    ], limit=1)

                    if status:
                        rec.previous_status_description_id = rec.last_status_description_id
                        rec.last_status_description_id = status.id

                    _logger.info(f'Vehicle {rec.name or rec.license_plate} - Tax period expired: '
                                 f'Status changed from "{old_status}" to "not_ready" '
                                 f'(Tax expired: {rec.end_of_tax_period})')
                    updated_count += 1
                else:
                    _logger.debug(f'Vehicle {rec.name or rec.license_plate} - Tax period still valid '
                                  f'({(rec.end_of_tax_period - today).days} days remaining)')

            except Exception as e:
                error_count += 1
                _logger.error(f'Error updating vehicle {rec.name or rec.license_plate} '
                              f'tax period status: {str(e)}')

        _logger.info(f'End of tax period update completed - Updated: {updated_count}, '
                     f'Errors: {error_count}, Total processed: {len(vehicles)}')

    @api.onchange('end_of_tax_period')
    def _onchange_end_of_tax_period_exp(self):
        self.update_last_status_vehicle_by_end_of_tax_period()

    @api.depends('end_of_tax_period')
    def _compute_end_of_tax_period_exp(self):
        today = date.today()
        for rec in self:
            is_expired = rec.end_of_tax_period and (rec.end_of_tax_period - today).days <= 30
            rec.is_end_of_tax_period_exp = is_expired

    def update_last_status_vehicle_by_stnk_expiration_period(self):
        """
        Update vehicle status berdasarkan masa berlaku STNK
        """
        today = fields.Date.today()
        updated_count = 0
        error_count = 0

        _logger.info('Starting update vehicle status by STNK expiration period')

        # Ambil semua kendaraan jika method dipanggil pada model tanpa recordset
        vehicles = self if self else self.search([])

        for rec in vehicles:
            try:
                if not rec.stnk_expiration_period:
                    continue

                is_expr_not_ready = (rec.stnk_expiration_period - today).days <= 0

                if is_expr_not_ready:
                    old_status = rec.vehicle_status
                    rec.vehicle_status = "not_ready"

                    status = self.env['fleet.vehicle.status'].search([
                        ('name_description', 'ilike', 'license not')
                    ], limit=1)

                    if status:
                        rec.previous_status_description_id = rec.last_status_description_id
                        rec.last_status_description_id = status.id

                    _logger.info(f'Vehicle {rec.name or rec.license_plate} - STNK expired: '
                                 f'Status changed from "{old_status}" to "not_ready" '
                                 f'(STNK expired: {rec.stnk_expiration_period})')
                    updated_count += 1
                else:
                    _logger.debug(f'Vehicle {rec.name or rec.license_plate} - STNK still valid '
                                  f'({(rec.stnk_expiration_period - today).days} days remaining)')

            except Exception as e:
                error_count += 1
                _logger.error(f'Error updating vehicle {rec.name or rec.license_plate} '
                              f'STNK expiration status: {str(e)}')

        _logger.info(f'STNK expiration update completed - Updated: {updated_count}, '
                     f'Errors: {error_count}, Total processed: {len(vehicles)}')

    @api.onchange('stnk_expiration_period')
    def _onchange_stnk_expiration_period_exp(self):
        self.update_last_status_vehicle_by_stnk_expiration_period()

    @api.depends('stnk_expiration_period')
    def _compute_stnk_expiration_period_exp(self):
        today = date.today()
        for rec in self:
            is_expired = rec.stnk_expiration_period and (rec.stnk_expiration_period - today).days <= 30
            rec.is_stnk_expiration_period_exp = is_expired

    @api.depends('stnk_expiration_period')
    def _compute_stnk_expiry(self):
        today = date.today()
        for stnk in self:
            stnk.is_stnk_expiring = stnk.stnk_expiration_period and (stnk.stnk_expiration_period - today).days <= 30

    @api.depends('no_lambung', 'license_plate')
    def compute_vehicle_name(self):
            for rec in self:
                rec.vehicle_name = f"{rec.no_lambung or ''} {'/'} {rec.license_plate or ''}".strip()

    @api.onchange('vehicle_id', 'geofence_checkpoint', 'maintenance_date', 'driver_confirmation',
                  'plan_armada_confirmation', 'geofence')
    def compute_vehicle_status(self):
        for rec in self:
            rec.vehicle_status = False
            if (rec.geofence_checkpoint is True and rec.maintenance_date is True and rec.driver_confirmation is True
                    and rec.plan_armada_confirmation is True):
                rec.vehicle_status = 'ready'

                status = self.env['fleet.vehicle.status'].search([
                    ('name_description', 'ilike', 'Ready for Use')
                ], limit=1)

                if status:
                    rec.last_status_description_id = status.id

            elif rec.geofence == 'loading':
                rec.vehicle_status = 'on_going'
            elif rec.geofence == 'unloading':
                rec.vehicle_status = 'on_return'
            elif (rec.geofence_checkpoint is False or rec.maintenance_date is False or rec.driver_confirmation is False
                  or rec.plan_armada_confirmation is False):
                rec.vehicle_status = 'not_ready'

                if rec.previous_status_description_id.id not in (24,25):
                    rec.last_status_description_id = rec.previous_status_description_id
            else:
                rec.vehicle_status = 'booked'

    #sorting vehicle based on context
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self._context.get('sort_fleet_vehicle'):  # Apply sorting only if context is set
            args = args or []
            recs = self.env['fleet.vehicle'].search(args, order="asset_type asc, date_of_status_ready asc, write_date asc", limit=limit)
            return recs.name_get()
        return super().name_search(name, args, operator, limit)

    # @api.depends('vehicle_id','geofence_checkpoint', 'maintenance_date','driver_confirmation','plan_armada_confirmation','geofence')
    # def compute_vehicle_status(self):
    #     for rec in self:
    #         rec.vehicle_status = False
    #         if (rec.geofence_checkpoint is True and rec.maintenance_date is True and rec.driver_confirmation is True
    #              and rec.plan_armada_confirmation is True):
    #              rec.vehicle_status = 'ready'
    #         elif rec.geofence == 'loading':
    #              rec.vehicle_status = 'on going'
    #         elif rec.geofence == 'unloading':
    #              rec.vehicle_status = 'on return'
    #         elif (rec.geofence_checkpoint is False or rec.maintenance_date is False or rec.driver_confirmation is False
    #              or rec.plan_armada_confirmation is False):
    #              rec.vehicle_status = 'not ready'
    #         else:
    #              rec.vehicle_status = 'booked'


    def warn(*args, **kwargs):
            pass
            import warnings
            warnings.warn = warn

    # def write(self, vals_list):
    #     list_depends = ['vehicle_id', 'geofence_checkpoint', 'maintenance_date',
    #                     'driver_confirmation', 'plan_armada_confirmation', 'geofence']
    #     if (name in vals_list for name in list_depends):
    #         for rec in self:
    #             if (rec.geofence_checkpoint and rec.maintenance_date and rec.driver_confirmation
    #                     and rec.plan_armada_confirmation):
    #                 if rec.geofence == 'loading':
    #                     rec.vehicle_status = 'on_going'
    #                 else:
    #                     rec.vehicle_status = 'ready'
    #             elif (not rec.geofence_checkpoint or not rec.maintenance_date or not rec.driver_confirmation
    #                   or not rec.plan_armada_confirmation):
    #                 rec.vehicle_status = 'not_ready'
    #             elif rec.geofence == 'unloading':
    #                 rec.vehicle_status = 'on_return'
    #             else:
    #                 rec.vehicle_status = 'booked'
    #     return super(FleetVehicle, self).write(vals_list)
    #
    # def _compute_vehicle_status(self):
    #     """Return computed status but does NOT override manual changes"""
    #     for rec in self:
    #         rec.vehicle_status = False
    #         if (rec.geofence_checkpoint and rec.maintenance_date and rec.driver_confirmation
    #                 and rec.plan_armada_confirmation):
    #             if rec.geofence == 'loading':
    #                 rec.vehicle_status = 'on_going'
    #             else:
    #                 rec.vehicle_status = 'ready'
    #         elif (not rec.geofence_checkpoint or not rec.maintenance_date or not rec.driver_confirmation
    #               or not rec.plan_armada_confirmation):
    #             rec.vehicle_status = 'not_ready'
    #         elif rec.geofence == 'unloading':
    #             rec.vehicle_status = 'on_return'
    #         else:
    #             rec.vehicle_status = 'booked'

    @api.model
    def write(self, vals):
        if 'last_status_description_id' in vals:
            for record in self:
                record.previous_status_description_id = record.last_status_description_id

        for record in self:
            if (record.geofence_checkpoint and record.maintenance_date and
                    record.driver_confirmation and record.plan_armada_confirmation):
                vals['date_of_status_ready'] = fields.Date.today()
                
        return super(FleetVehicle, self).write(vals)

    @api.model
    def fetch_api_data_vehicle(self, val=None): #fetch master data untuk vehicle dari VMS
        """ Fetches data from a third-party API """
        url = "https://vtsapi.easygo-gps.co.id/api/Master/vehicles"  # Replace with your API URL
        headers = {
            "accept": "application/json",
            "token": "55AEED3BF70241F8BD95EAB1DB2DEF67",  # If needed
            "Content-Type": "application/json",
        }
        body = {
            "nopol": ""
        }
        try:
            response = requests.post(url, headers=headers, json=body)
            log_message = f"API Response Status: {response.status_code}"
            self.log_message(log_message, "info")

            if response.status_code != 200:
                raise UserError(f"API Error {response.status_code}: {response.text}")

            data = response.json()  # Convert response to JSON

            # Process and store data in Odoo
            vehicles = data['Data']
            total = 0
            for vec_cn in vehicles:
                vehicle = self.search([('vin_sn', '=', vec_cn['chasis_no'])])
                if vehicle:
                    total += 1
                    print(total)
                    vehicle.vehicle_id = vec_cn.get('vehicle_id', False)
                    log_message = f"Updated vehicle_id for chasis {vec_cn['chasis_no']}: {vec_cn.get('vehicle_id')}"
                    self.log_message(log_message, "info")
                else:
                    log_message = f"nomor chasis: {vec_cn['chasis_no']} tidak ada"
                    self.log_message(log_message, "info")
            return {"status": "success", "message": "Data successfully fetched"}

        except requests.exceptions.RequestException as e:
            error_message = f"API Request Failed: {str(e)}"
            self.log_message(error_message, "error")  # Log as an error
            raise UserError(error_message)

    def log_message(self, message, level="info"):
        """Helper method to log messages in ir.logging"""
        self.env['ir.logging'].create({
            'name': 'API Request',
            'type': 'server',
            'level': level,
            'dbname': self._cr.dbname,
            'message': message,
            'path': 'custom_module.fleet_vehicle',
            'func': 'fetch_vehicles_from_api',
            'line': '0',
        })

    #def _get_current_time(self):
    #    for li in self:
    #        li.current_time = fields.datetime.now()

    @api.onchange('driver_confirmation')
    def update_status_availability_driver(self):
        for rec in self:
            if rec.driver_id:
                if rec.driver_confirmation:
                    rec.driver_id.availability = 'Ready'
                else:
                    rec.driver_id.availability = 'On Duty'

    def action_select_vehicle(self):
        """
        Action untuk select vehicle dari popup dan close popup
        """
        # Get fleet_do_id from context
        fleet_do_id = self.env.context.get('fleet_do_id')

        if fleet_do_id:
            # Set vehicle to fleet.do record
            fleet_do = self.env['fleet.do'].browse(fleet_do_id)
            fleet_do.set_selected_vehicle(self.id)

            # Return action to close popup and refresh form
            return {
                'type': 'ir.actions.act_window_close',
                'effect': {
                    'fadeout': 'slow',
                    'message': f'Vehicle {self.name} selected successfully!',
                    'type': 'rainbow_man',
                }
            }

        return {'type': 'ir.actions.act_window_close'}

    def select_vehicle(self):
        """Method untuk handle selection vehicle dari popup"""
        fleet_do_id = self.env.context.get('fleet_do_id')
        if fleet_do_id:
            # Update fleet DO dengan vehicle yang dipilih
            fleet_do = self.env['fleet.do'].browse(fleet_do_id)  # sesuaikan dengan model name Anda
            fleet_do.write({'vehicle_id': self.id})

        return {
            'type': 'ir.actions.act_window_close',
        }

    def action_select_and_close(self):
        """Alternative method with different name"""
        return self.select_vehicle()

    def create_driver_history(self, vals):
        # Only update driver history if driver_id is being changed
        if 'driver_id' in vals and vals.get('driver_id'):
            # Get the current/newest driver history record for this vehicle
            newest_history = self.env['fleet.vehicle.assignation.log'].search([
                ('vehicle_id', '=', self.id),
            ], order="id desc", limit=1)

            # Close the previous driver assignment
            if newest_history:
                newest_history.write({'date_end': fields.Date.today()})

        return super().create_driver_history(vals)

    @api.onchange('driver_id')
    def onchange_driver_id(self):
        for rec in self:
            if str(rec.id).startswith("NewId_"):
                vehicle_id = str(rec.id)[6:]  # ambil mulai index ke-6
            else:
                vehicle_id = rec.id

            dos = self.env['fleet.do'].search([
                # ('state', '!=', 'done'),
                ('vehicle_id.id', '=', vehicle_id),
            ])
            print('dos -> ', dos, vehicle_id)

            for do in dos:
                if do.state not in ('cancel', 'done'):
                    do.driver_id = rec.driver_id

            bank = rec.driver_id.bank_name_ids
            if not bank:
                raise ValidationError("Driver belum memiliki data rekening. Mohon lengkapi terlebih dahulu!")

            for do in dos:
                if do.state not in ('cancel', 'done'):
                    prev_bank = do.driver_id.bank_name_ids
                    prev_bank = prev_bank[0]
                    bank = bank[0]

                    do.rekening_number = bank.acc_number
                    do.rekening_name = bank.acc_holder_name
                    do.rekening_bank = bank.bank_id.name
                    do.transfer_to = rec.driver_id

                    self.env['fleet.do.log'].create({
                        'do_id': do.id,
                        'prev_driver_id': do.driver_id.id,
                        'driver_id': rec.driver_id.id,
                        'prev_rekening_number': prev_bank.acc_number,
                        'prev_rekening_name': prev_bank.acc_holder_name,
                        'prev_rekening_bank': prev_bank.bank_id.name,
                        'rekening_number': bank.acc_number,
                        'rekening_name': bank.acc_holder_name,
                        'rekening_bank': bank.bank_id.name,
                    })

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        # Filter berdasarkan company yang dipilih user
        domain = domain or []

        # Cek apakah sudah ada filter company_id
        has_company_filter = any(
            term[0] == 'company_id'
            for term in domain
            if isinstance(term, (list, tuple)) and len(term) >= 3
        )

        if not has_company_filter:
            # Tambahkan filter company_ids dari context atau env.companies
            company_ids = self.env.context.get('allowed_company_ids', self.env.companies.ids)
            domain = domain + [('company_id', 'in', company_ids)]

        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid
        )

class VehicleTargetLine(models.Model):
    _name = 'vehicle.target.line'
    _rec_name = 'vehicle_id'

    vehicle_id = fields.Many2one('fleet.vehicle')
    year =  fields.Integer('Year')
    month = fields.Integer('Month')
    total_target = fields.Integer('Total Target in Month')
    actual_target = fields.Integer('Actual Target in Month', compute='_compute_actual_target', store=True)
    target_days_utilization = fields.Integer('Target Days Utilization')

    @api.model
    def date_is_match(self, datetime_str, year, month):
        """
        Memeriksa apakah tahun dan bulan yang diberikan cocok dengan datetime string

        :param datetime_str: String datetime dalam format 'YYYY-MM-DD HH:MM:SS' atau objek datetime
        :param year: Tahun yang akan dibandingkan (string atau integer)
        :param month: Bulan yang akan dibandingkan (string atau integer)
        :return: Boolean True jika cocok, False jika tidak
        """
        try:
            print("masukkkkkkkkkkkkkk")
            # Penanganan jika datetime_str adalah None
            if not datetime_str:
                return False

            # Cek apakah datetime_str sudah berbentuk objek datetime atau masih string
            if isinstance(datetime_str, str):
                # Coba format standar terlebih dahulu
                try:
                    dt_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Coba format alternatif yang mungkin digunakan Odoo
                    try:
                        dt_obj = datetime.strptime(datetime_str, '%Y-%m-%d')
                    except ValueError:
                        # Jika masih gagal, coba format datetime dengan timezone
                        dt_obj = datetime.strptime(datetime_str.split('+')[0].strip(), '%Y-%m-%d %H:%M:%S')
            else:
                # Jika sudah berupa objek datetime
                dt_obj = datetime_str

            # Konversi parameter ke string untuk perbandingan yang konsisten
            year_str = str(year)
            month_str = str(month).zfill(2)  # Memastikan format bulan menjadi 2 digit

            # Ekstrak tahun dan bulan dari objek datetime dan bandingkan
            dt_year = dt_obj.strftime('%Y')
            dt_month = dt_obj.strftime('%m')

            # Log untuk debugging
            print("Comparing dates - Input: ", dt_year, dt_month, year_str, month_str)

            # Return hasil perbandingan
            return dt_year == year_str and dt_month == month_str

        except Exception as e:
            # Catat error lebih detail untuk memudahkan debugging
            print(f"Error saat memeriksa tanggal: {str(e)}")
            return False

    @api.depends('vehicle_id', 'year', 'month')
    def _compute_actual_target(self):
        for target_line in self:
            total = 0
            fleet_dos = self.env['fleet.do'].search([
                ('vehicle_id', '=', target_line.vehicle_id.id),
                ('state', '=', 'done'),
            ])
            print(fleet_dos)
            for do in fleet_dos:
                if self.date_is_match(do.date, target_line.year, target_line.month):
                    # Perbaikan: Menggunakan order_line bukan line_ids untuk sale.order
                    for line in do.po_line_ids:
                        total += line.price_unit
                else:
                    total = 0
            target_line.actual_target = total