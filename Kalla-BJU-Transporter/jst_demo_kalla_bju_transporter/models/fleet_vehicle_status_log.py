from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class FleetVehicleStatusLog(models.Model):
    _name = 'fleet.vehicle.status.log'

    # Menambahkan constraint SQL untuk memastikan kombinasi vehicle_id dan date unik
    _sql_constraints = [
        ('unique_vehicle_date_status', 'UNIQUE(vehicle_id, date, last_status_description_id)',
         'Vehicle cannot have duplicate entries for the same date and status description!')
    ]

    date = fields.Date('Date', required=True)
    vehicle_status = fields.Selection([
        ('ready', 'Ready'),
        ('on_going', 'On Going'),
        ('on_return', 'On Return'),
        ('not_ready', 'Not Ready')], string='Last Status', default='not_ready', tracking=True, required=True)
    last_status_description_id = fields.Many2one(
        'fleet.vehicle.status',
        domain="[('vehicle_status','=',vehicle_status)]",
        string="Last Status Description",
        tracking=True,
        required=True
    )
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True)
    prev_status = fields.Char()
    prev_status_description = fields.Char()
    prev_status_description_id = fields.Integer()

    @api.constrains('vehicle_id', 'date', 'last_status_description_id')
    def _check_unique_vehicle_date_status(self):
        """Validasi untuk memastikan tidak ada duplikasi vehicle_id, date, dan last_status_description_id"""
        for record in self:
            existing_record = self.search([
                ('vehicle_id', '=', record.vehicle_id.id),
                ('date', '=', record.date),
                ('last_status_description_id', '=', record.last_status_description_id.id),
                ('id', '!=', record.id)
            ])
            if existing_record:
                raise ValidationError(
                    _('Kendaraan "%s" sudah memiliki entri log status untuk tanggal %s dengan deskripsi status "%s". '
                      'Silakan pilih tanggal, kendaraan, atau deskripsi status yang berbeda.') %
                    (record.vehicle_id.name, record.date, record.last_status_description_id.name_description)
                )

    def _get_previous_status_info(self, vehicle_id):
        """Helper method to get previous status and status description from vehicle"""
        if vehicle_id:
            vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
            prev_status = vehicle.vehicle_status if hasattr(vehicle, 'vehicle_status') else False
            prev_status_desc = vehicle.last_status_description_id.name_description if vehicle.last_status_description_id else False
            prev_status_description_id = vehicle.last_status_description_id or False
            return prev_status, prev_status_desc, prev_status_description_id
        return False, False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date') and vals.get('vehicle_id'):
                # Ambil previous status dan status description sebelum update
                prev_status, prev_status_desc, prev_status_description_id = self._get_previous_status_info(vals['vehicle_id'])
                print('prev_status, prev_status_desc, prev_status_description_id', prev_status, prev_status_desc, prev_status_description_id)
                if prev_status:
                    vals['prev_status'] = prev_status
                if prev_status_desc:
                    vals['prev_status_description'] = prev_status_desc
                    vals['prev_status_description_id'] = prev_status_description_id.id

                # Konversi vals['date'] ke objek date jika berupa string
                if isinstance(vals['date'], str):
                    vals_date = fields.Date.from_string(vals['date'])
                else:
                    vals_date = vals['date']

                # Dapatkan tanggal hari ini
                today = date.today()

                # Cek apakah tanggal sama dengan hari ini
                if vals_date == today:
                    # Tanggal sama dengan hari ini
                    print("Date is today!")
                    vehicle = self.env['fleet.vehicle'].browse(vals['vehicle_id'])
                    if 'vehicle_status' in vals and vals['vehicle_status'] == 'not_ready':
                        vehicle.vehicle_status = vals['vehicle_status']
                    vehicle.last_status_description_id = vals['last_status_description_id']
                    vehicle.geofence_checkpoint = False
                    vehicle.driver_confirmation = False
                    vehicle.plan_armada_confirmation = False

        return super().create(vals_list)

    def write(self, vals):
        # Cek jika ada perubahan pada date atau vehicle_id atau last_status_description_id
        if vals.get('date') or vals.get('vehicle_id') or vals.get('last_status_description_id'):
            for record in self:
                # Ambil date dari vals atau gunakan date yang sudah ada di record
                record_date = vals.get('date', record.date)

                # Jika tanggal berubah, ambil previous status dan status description
                if vals.get('date') and vals['date'] != record.date:
                    vehicle_id = vals.get('vehicle_id', record.vehicle_id.id)
                    prev_status, prev_status_desc, prev_status_description_id = self._get_previous_status_info(vehicle_id)
                    if prev_status:
                        vals['prev_status'] = prev_status
                    if prev_status_desc:
                        vals['prev_status_description'] = prev_status_desc
                        vals['prev_status_description_id'] = prev_status_description_id.id

                # Konversi ke objek date jika berupa string
                if isinstance(record_date, str):
                    record_date = fields.Date.from_string(record_date)

                # Dapatkan tanggal hari ini
                today = date.today()

                # Cek apakah tanggal sama dengan hari ini
                if record_date == today:
                    # Tanggal sama dengan hari ini
                    print("Date is today!")

                    # Ambil vehicle_id dari vals atau gunakan yang sudah ada di record
                    vehicle_id = vals.get('vehicle_id', record.vehicle_id.id)
                    last_status_description_id = vals.get('last_status_description_id',
                                                          record.last_status_description_id.id)
                    vehicle_status = vals.get('vehicle_status', record.vehicle_status)

                    if vehicle_id and last_status_description_id:
                        vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
                        if 'vehicle_status' in vals and vehicle_status == 'not_ready':
                            vehicle.vehicle_status = vehicle_status
                        vehicle.last_status_description_id = last_status_description_id
                        vehicle.geofence_checkpoint = False
                        vehicle.driver_confirmation = False
                        vehicle.plan_armada_confirmation = False

        return super().write(vals)

    def unlink(self):
        for rec in self:
            record_date = rec.date
            # Konversi ke objek date jika berupa string
            if isinstance(record_date, str):
                record_date = fields.Date.from_string(record_date)

            # Dapatkan tanggal hari ini
            today = date.today()

            if today == record_date:
                rec.vehicle_id.vehicle_status = rec.prev_status
                rec.vehicle_id.last_status_description_id = rec.prev_status_description_id

        return super().unlink()