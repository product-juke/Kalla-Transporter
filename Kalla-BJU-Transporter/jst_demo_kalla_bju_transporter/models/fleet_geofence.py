from odoo import api, fields, models
import requests
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)

class FleetGeofence(models.Model):

    _name = 'fleet.geofence'
    _rec_name = 'geo_nm'
    _description = 'Geofence'

    geo_id = fields.Integer('Geo ID')
    geo_code = fields.Char('Geo Code')
    geo_nm  = fields.Char('Geo Name')
    type = fields.Char('Type')
    shape_nm = fields.Char('Shape Name')
    colo = fields.Char('Colo')
    geo_type_nm = fields.Char('Geo Type Name')
    tag_nm = fields.Char('Tag Name')

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

    def action_update_list_data(self):
        self.hit_endpoint_scheduler(called_from_ui=True)

    @api.model
    def hit_endpoint_scheduler(self, called_from_ui=False):
        """Method yang akan dijalankan oleh scheduler untuk hit endpoint"""
        try:
            base_external_api_url = 'https://vtsapi.easygo-gps.co.id'
            endpoint = f"{base_external_api_url}/api/geofence/masterdata"

            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "token": "55AEED3BF70241F8BD95EAB1DB2DEF67",
            }
            params = {
                "tipe": None,
                "code": "",
                "nama": "",
                "include_upline_downline": 0
            }

            # Melakukan HTTP request
            response = requests.post(endpoint, headers=headers, json=params)

            # Log response
            _logger.info(f"=== GEOFENCE ===> Endpoint hit successful: {endpoint} -> {response.status_code}")
            _logger.info(f"=== GEOFENCE ===> Response: {response.text}")

            external_data = response.json()
            _logger.info(f"=== GEOFENCE ===> Parse JSON: {external_data}")
            data_list = external_data.get('Data', [])
            stored_count, skipped_count = self._store_geofence_data(data_list)
            
            message = f"✅ Successfully update last geofence data. Total: {len(data_list)}, Stored: {stored_count}, Skipped: {skipped_count}"
            if called_from_ui: self._notify_success(message)

            return True
        except Exception as e:
            error_message = f"❌ Failed to update last geofence data: {str(e)}"
            _logger.error(f"=== GEOFENCE ===> Error hitting endpoint: {str(e)}")

            # Tampilkan notifikasi error
            if called_from_ui: self._notify_error(error_message)
            return False

    def _store_geofence_data(self, data_list):
        fleet_geofence = self.env["fleet.geofence"].sudo()
        _logger.info(f"=== GEOFENCE ===> Length Data: {len(data_list)}")
        stored_count = 0
        skipped_count = 0

        if len(data_list) > 0:
            for index, data in enumerate(data_list):
                domain = [
                    ("geo_id", "=", data["geo_id"]),
                    ("geo_code", "=", data["geo_code"]),
                    ("geo_nm", "=", data["geo_nm"]),
                ]

                exists = fleet_geofence.search(domain, limit=1)
                if exists:
                    _logger.info(f"=== GEOFENCE ===> [{index}] Lewati data duplikat: %s", data)
                    skipped_count += 1
                    continue
                else:
                    _logger.info(f"=== GEOFENCE ===> [{index}] Menyimpan data: %s", data)

                    fleet_geofence.create(
                        {
                            "geo_id": data["geo_id"],
                            "geo_code": data["geo_code"],
                            "geo_nm": data["geo_nm"],
                            "type": data["tipe"],
                            "shape_nm": data["shape_nm"],
                            "colo": data["colo"],
                            "geo_type_nm": data["geo_type_nm"],
                            "tag_nm": data["tag_nm"],
                        }
                    )
                    stored_count += 1

        _logger.info(
            f"=== GEOFENCE ===> Total data: {len(data_list)}, Tersimpan: {stored_count}, Dilewati: {skipped_count}"
        )
        return stored_count, skipped_count 
