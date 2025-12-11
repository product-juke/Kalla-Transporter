from odoo import fields, models, api
import logging
import requests
from datetime import datetime

_logger = logging.getLogger(__name__)


class FleetRoute(models.Model):
    _name = 'm.fleet.route'
    _rec_name = 'geo_code'
    _description = 'Master Data Route'

    autoid = fields.Integer(string='Auto ID')
    geo_code = fields.Char(string='Geo Code')
    geo_nm = fields.Char(string='Geo Name')
    color = fields.Char(string='Color', size=6)  # HEX color code, misal "F5F5F5"
    radius = fields.Integer(string='Radius (meters)')
    alert = fields.Boolean(string='Alert')
    geo_id_asal = fields.Integer(string='Geo ID Asal')
    geo_id_tujuan = fields.Integer(string='Geo ID Tujuan')
    enabled = fields.Boolean(string='Enabled', default=True)
    geo_asal_code = fields.Char(string='Geo Asal Code')
    geo_asal_name = fields.Char(string='Geo Asal Name')
    geo_tujuan_code = fields.Char(string='Geo Tujuan Code')
    geo_tujuan_name = fields.Char(string='Geo Tujuan Name')

    def _notify_success(self, message):
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
            'title': 'Success!',
            'message': message,
            'type': 'success',
        })

    def _notify_error(self, message):
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
            'title': 'Error!',
            'message': message,
            'type': 'danger',
        })
    
    def action_update_list_data(self):
      self.hit_endpoint_scheduler(called_from_ui=True)

    @api.model
    def hit_endpoint_scheduler(self, called_from_ui=False):
        """Method yang akan dijalankan oleh scheduler untuk hit endpoint"""
        try:
            base_external_api_url = 'https://vtsapi.easygo-gps.co.id'
            # URL dari ir.config_parameter
            # base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            endpoint = f"{base_external_api_url}/api/Route/masterdata"

            headers = {
              'accept': 'application/json',
              'Content-Type': 'application/json',
              'token': '55AEED3BF70241F8BD95EAB1DB2DEF67',
              # 'Host': base_external_api_url,
            }
            params = {
                'search_param': "",
                'page': 0,
                'limit': 0,
            }
            
            # Melakukan HTTP request
            response = requests.post(endpoint, headers=headers, json=params)
            
            # Log response
            _logger.info(f"=== MR ===> Endpoint hit successful: {endpoint} -> {response.status_code}")
            _logger.info(f"=== MR ===> Response: {response.text}")

            external_data = response.json()
            _logger.info(f"=== MR ===> Parse JSON: {external_data}")
            data_list = external_data.get('Data', [])
            stored_count, skipped_count = self._store_master_route_data(data_list)
            
            message = f"✅ Successfully update route data. Total: {len(data_list)}, Stored: {stored_count}, Skipped: {skipped_count}"
            if called_from_ui: self._notify_success(message)

            return True
        except Exception as e:
            error_message = f"❌ Failed to update route data: {str(e)}"
            _logger.error(f"=== MR ERR ===> Error hitting endpoint: {str(e)}")
            
            # Tampilkan notifikasi error
            if called_from_ui: self._notify_error(error_message)
            return False
    
    def _store_master_route_data(self, data_list):
        m_fleet_route = self.env['m.fleet.route'].sudo()
        _logger.info(f"=== MR ===> Length Data: {len(data_list)}")
        stored_count = 0
        skipped_count = 0
        
        if len(data_list) > 0:
            for index, data in enumerate(data_list):
                domain = [
                    ('autoid', '=', data['autoid']),
                    ('geo_code', '=', data['geo_code']), 
                    ('geo_asal_code', '=', data['geo_asal_code']),
                    ('geo_asal_name', '=', data['geo_asal_name']),
                    ('geo_tujuan_code', '=', data['geo_tujuan_code']),
                    ('geo_tujuan_name', '=', data['geo_tujuan_name']),
                ]
                
                exists = m_fleet_route.search(domain, limit=1)
                if exists:
                    _logger.info(f"=== MR ===> [{index}] Lewati data duplikat: %s", data)
                    skipped_count += 1
                    continue
                else:
                    _logger.info(f"=== MR ===> [{index}] Menyimpan data: %s", data)

                    m_fleet_route.create({
                        'autoid': data['autoid'],
                        'geo_code': data['geo_code'],
                        'geo_nm': data['geo_nm'],
                        'color': data['color'],
                        'radius': data['radius'],
                        'alert': data['alert'],
                        'geo_id_asal': data['geo_id_asal'],
                        'geo_id_tujuan': data['geo_id_tujuan'],
                        'enabled': data['enabled'],
                        'geo_asal_code': data['geo_asal_code'],
                        'geo_asal_name': data['geo_asal_name'],
                        'geo_tujuan_code': data['geo_tujuan_code'],
                        'geo_tujuan_name': data['geo_tujuan_name'],
                    })
                    stored_count += 1

        _logger.info(f"=== MR ===> Total data: {len(data_list)}, Tersimpan: {stored_count}, Dilewati: {skipped_count}")
        return stored_count, skipped_count