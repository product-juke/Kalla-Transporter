from odoo import models, fields, api, _
from datetime import date


class FleetVehicleStatusLog(models.Model):
    _inherit = 'fleet.vehicle.status.log'

    @api.model_create_multi
    def create(self, vals_list):
        results = super().create(vals_list)
        print('res => ', results)
        for res in results:
            if res and res.id:
                util_data = self.env['trx.vehicle.utilization'].search([
                    ('date', '=', res.date),
                    ('plate_no', '=', res.vehicle_id.license_plate),
                    ('vehicle_name', '=', res.vehicle_id.name),
                ])

                status = res.last_status_description_id.name_description.upper()
                if status == 'DRIVER NOT':
                    status = 'DRIVER NOT READY'

                self.env['trx.vehicle.non.utilization'].create({
                    'vehicle_status_log_id': res.id,
                    'date': res.date,
                    'plate_no': res.vehicle_id.license_plate,
                    'status_plan': status,
                    'status_actual': status,
                    'vehicle_name': res.vehicle_id.name,
                    'do_no_lms': None,
                    'do_no_tms': None,
                    'driver': res.vehicle_id.driver_id.name if res.vehicle_id.driver_id else None,
                    'branch_project': util_data.branch_project if util_data else None,
                })
        return results

    def write(self, vals):
        # Cek jika ada perubahan pada date atau vehicle_id
        if vals.get('date') or vals.get('vehicle_id') or vals.get('last_status_description_id'):
            for record in self:
                # Ambil date dari vals atau gunakan date yang sudah ada di record
                record_date = vals.get('date', record.date)

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
                        if vehicle_status == 'not_ready':
                            vehicle.vehicle_status = vehicle_status
                        vehicle.last_status_description_id = last_status_description_id
                        vehicle.geofence_checkpoint = False
                        vehicle.driver_confirmation = False
                        vehicle.plan_armada_confirmation = False

        res = super().write(vals)
        if res and self.id:
            util_data = self.env['trx.vehicle.utilization'].search([
                ('date', '=', self.date),
                ('plate_no', '=', self.vehicle_id.license_plate),
                ('vehicle_name', '=', self.vehicle_id.name),
            ])

            status = self.last_status_description_id.name_description.upper()
            if status == 'DRIVER NOT':
                status = 'DRIVER NOT READY'

            query = """
                UPDATE trx_vehicle_non_utilization
                SET date = %s, status_plan = %s, status_actual = %s
                WHERE vehicle_status_log_id = %s
            """
            params = (self.date, status, status, self.id)

            if util_data:
                query = """
                    UPDATE trx_vehicle_non_utilization
                    SET date = %s, status_plan = %s, status_actual = %s, branch_project = %s
                    WHERE vehicle_status_log_id = %s
                """
                params = (self.date, status, status, util_data.branch_project or None, self.id)

            self.env.cr.execute(query, params)

        return res

    def unlink(self):
        for rec in self:
            query_delete = """
                DELETE FROM trx_vehicle_non_utilization
                WHERE plate_no = %s AND vehicle_name = %s AND date = %s
            """
            self.env.cr.execute(query_delete, (rec.vehicle_id.license_plate, rec.vehicle_id.name, rec.date))
            self.env.cr.commit()

        return super().unlink()