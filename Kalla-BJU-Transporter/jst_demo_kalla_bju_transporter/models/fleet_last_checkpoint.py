from odoo import api, fields, models
import requests
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class FleetLastCheckpoint(models.Model):
    _name = "fleet.last.checkpoint"
    _rec_name = 'vehicle_code'
    _description = "Fleet Last Checkpoint"

    vehicle_id = fields.Char(string="Vehicle ID")
    vehicle_code = fields.Many2one("fleet.vehicle")
    nopol = fields.Char(string="Nomor Polisi")
    nomor_do = fields.Char(string="Nomor DO")
    group_name = fields.Char(string="Group Name")

    start_time = fields.Datetime(string="Start Time")
    stop_time = fields.Datetime(string="Stop Time")

    start_acc = fields.Selection([("ON", "ON"), ("OFF", "OFF")], string="Start ACC")
    stop_acc = fields.Selection([("ON", "ON"), ("OFF", "OFF")], string="Stop ACC")

    start_speed = fields.Integer(string="Start Speed")
    stop_speed = fields.Integer(string="Stop Speed")

    code_cp_a = fields.Char(string="Code CP A")
    code_cp_b = fields.Char(string="Code CP B")

    event = fields.Selection([("IN", "IN"), ("OUT", "OUT")], string="Event")

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        for record in res:
            if hasattr(record, 'event') and record.event and hasattr(record, 'vehicle_code') and record.vehicle_code:
                # Lakukan sesuatu dengan field event dari record
                print(f"Created record with event: {record.event}")
                
                today = fields.Date.today()
                stop_time = fields.Datetime.from_string(record['stop_time'])
                if stop_time.date() == today:
                    if record['event'].lower() == 'out':
                        if record["code_cp_a"] == 'CR2' and record["code_cp_b"] == 'CR1':
                            record.vehicle_code.forecast_status_ready = 'Ready for Use'

                # Contoh: Jika event adalah Many2one field
                if str(record.event).lower() == 'out':
                    record.vehicle_code.geofence_checkpoint = False
                    record.vehicle_code.driver_confirmation = False
                    record.vehicle_code.plan_armada_confirmation = False
                else:
                    record.vehicle_code.geofence_checkpoint = True

        return res

    def _notify_success(self, message):
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": "Success!",
                "message": message,
                "type": "success",
            },
        )

    def _notify_error(self, message):
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": "Error!",
                "message": message,
                "type": "danger",
            },
        )

    def action_update_list_data(self, start_date=None, end_date=None):
        _logger.info(f"=== LC ===> Sync Data mulai {start_date} sampai {end_date}")
        return self.hit_endpoint_scheduler(called_from_ui=True, start_date=start_date, end_date=end_date)

    @api.model
    def hit_endpoint_scheduler(self, called_from_ui=False, start_date=None, end_date=None):
        """Method yang akan dijalankan oleh scheduler untuk hit endpoint"""
        try:
            base_external_api_url = 'https://vtsapi.easygo-gps.co.id'
            # URL dari ir.config_parameter
            # base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            endpoint = f"{base_external_api_url}/api/kalla/report/checkpoint"

            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "token": "55AEED3BF70241F8BD95EAB1DB2DEF67",
                # "Host": "vtsapi.easygo-gps.co.id",
            }

            if not start_date or not end_date:
                today_str = date.today().strftime('%Y-%m-%d')
                start_time = f"{today_str} 00:00:01"
                stop_time = f"{today_str} 23:59:59"
            else:
                start_time = f"{start_date.strftime('%Y-%m-%d')} 00:00:01"
                stop_time = f"{end_date.strftime('%Y-%m-%d')} 23:59:59"

            _logger.info(f"=== LC ===> Tanggal Mulai: {start_time}")
            _logger.info(f"=== LC ===> Tanggal Berhenti: {stop_time}")
            params = {
                'start_time': start_time,
                'stop_time': stop_time,
                'nopol': "",
                'event': "",
            }

            # Melakukan HTTP request
            response = requests.post(endpoint, headers=headers, json=params)

            # Log response
            _logger.info(f"=== LC ===> Endpoint hit successful: {endpoint} -> {response.status_code}")
            _logger.info(f"=== LC ===> Response: {response.text}")

            external_data = response.json()
            _logger.info(f"=== LC ===> Parse JSON: {external_data}")
            data_list = external_data.get('Data', [])
            stored_count, skipped_count, vehicles = self._store_checkpoint_data(data_list)
            
            message = f"✅ Successfully update last checkpoint data. Total: {len(data_list)}, Stored: {stored_count}, Skipped: {skipped_count}"
            if called_from_ui: self._notify_success(message)

            return {
                'success': True,
                'vehicles': vehicles
            }
        except Exception as e:
            error_message = f"❌ Failed to update last checkpoint data: {str(e)}"
            _logger.error(f"=== LC ===> Error hitting endpoint: {str(e)}")

            # Tampilkan notifikasi error
            if called_from_ui: self._notify_error(error_message)
            return False

    def _store_checkpoint_data(self, data_list):
        fleet_last_checkpoint = self.env["fleet.last.checkpoint"].sudo()
        _logger.info(f"=== LC ===> Length Data: {len(data_list)}")
        vehicles = []

        stored_count = 0
        skipped_count = 0

        nopol_latest_data = {}
        today = fields.Date.today()

        if len(data_list) > 0:
            for index, data in enumerate(data_list):
                if "start_time" in data and data["start_time"]:
                    # Ubah format '2025-04-24T08:20:17+07:00' menjadi '2025-04-24 08:20:17'
                    try:
                        # Parse waktu ISO 8601
                        dt = datetime.fromisoformat(data["start_time"])
                        # Format ulang tanpa timezone
                        data["start_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")

                        if data["nopol"] not in nopol_latest_data or dt > nopol_latest_data[data["nopol"]]["_dt"]:
                            data["_dt"] = dt
                            nopol_latest_data[data["nopol"]] = data

                    except (ValueError, TypeError) as e:
                        _logger.error(
                            f"=== LC ===> Error converting start_time: {data['start_time']} - {str(e)}"
                        )

                if "stop_time" in data and data["stop_time"]:
                    try:
                        dt = datetime.fromisoformat(data["stop_time"])
                        data["stop_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError) as e:
                        _logger.error(
                            f"=== LC ===> Error converting stop_time: {data['stop_time']} - {str(e)}"
                        )

                domain = [
                    ("nopol", "=", data["nopol"]),
                    ("start_time", "=", data["start_time"]),
                    ("stop_time", "=", data["stop_time"]),
                    ("code_cp_a", "=", data["code_cp_a"]),
                    ("code_cp_b", "=", data["code_cp_b"]),
                ]

                exists = fleet_last_checkpoint.search(domain, limit=1)
                if exists:
                    _logger.info(f"=== LC ===> [{index}] Lewati data duplikat: %s", data)
                    skipped_count += 1
                    continue
                else:
                    _logger.info(f"=== LC ===> [{index}] Menyimpan data: %s", data)

                    vehicle = self.env["fleet.vehicle"].search(
                        [("license_plate", "=", data["nopol"])], limit=1
                    )
                    
                    vehicles.append(vehicle)
                    fleet_last_checkpoint.create(
                        {
                            "vehicle_id": data["vehicle_id"],
                            "vehicle_code": vehicle.id,
                            "nopol": data["nopol"],
                            "group_name": data["group_name"],
                            "start_time": data["start_time"],
                            "stop_time": data["stop_time"],
                            "start_acc": data["start_acc"],
                            "stop_acc": data["stop_acc"],
                            "start_speed": data["start_speed"],
                            "stop_speed": data["stop_speed"],
                            "code_cp_a": data["code_cp_a"],
                            "code_cp_b": data["code_cp_b"],
                            "event": data["event"],
                        }
                    )
                    stored_count += 1
                    
                    stop_time = fields.Datetime.from_string(data['stop_time'])
                    if stop_time.date() == today:
                        if data['event'].lower() == 'out':
                            if data["code_cp_a"] == 'CR2' and data["code_cp_b"] == 'CR1':
                                vehicle.forecast_status_ready = 'Ready for Use'
                                    
                    

                    # set status and geofence checkpoint vehicle
                    if data['event'].lower() == 'out':
                        vehicle.geofence_checkpoint = False
                        vehicle.driver_confirmation = False
                        vehicle.plan_armada_confirmation = False
                    else:
                        vehicle.geofence_checkpoint = True
                        # vehicle.vehicle_status = 'on_going'

            for nopol, latest_data in nopol_latest_data.items():
                vehicle = self.env["fleet.vehicle"].search(
                    [("license_plate", "=", nopol)], limit=1
                )
                if not vehicle:
                    continue

                if latest_data['event'].lower() == 'out':
                    vehicle.geofence_checkpoint = False
                    vehicle.driver_confirmation = False
                    vehicle.plan_armada_confirmation = False

                    # vehicle.vehicle_status = 'on_return'
                    # status = self.env['fleet.vehicle.status'].search([
                    #     ('name_description', 'ilike', 'One The Way Pool')
                    # ], limit=1)
                else:
                    vehicle.geofence_checkpoint = True

                    # vehicle.vehicle_status = 'on_going'
                    # status = self.env['fleet.vehicle.status'].search([
                    #     ('name_description', 'ilike', 'Loading')
                    # ], limit=1)

                # if status:
                #     vehicle.last_status_description_id = status.id

        _logger.info(
            f"=== LC ===> Total data: {len(data_list)}, Tersimpan: {stored_count}, Dilewati: {skipped_count}"
        )
        return stored_count, skipped_count, vehicles

    def action_open_sync_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pilih Tanggal',
            'res_model': 'fleet.last.checkpoint.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
