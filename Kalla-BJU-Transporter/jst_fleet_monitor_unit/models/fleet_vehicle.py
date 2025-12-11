from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    def action_monitor_unit(self):
        """Open wizard to input monitoring duration"""
        return {
            'name': 'Monitor Unit',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.monitor.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_vehicle_id': self.id},
        }

    def create_share_link(self, duration_hours, api_token):
        """Create share link via EasyGo GPS API"""
        if not self.license_plate:
            return {'success': False, 'message': 'No license plate found'}

        url = "https://vtsapi.easygo-gps.co.id/api/ShareLink/new"
        headers = {
            'Content-Type': 'application/json',
            'Token': api_token
        }

        payload = {
            'nopol': self.license_plate,
            'active_do': 1,
            'duration_type': 'HOUR',
            'sharing_time': str(duration_hours)
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            response.raise_for_status()

            result = response.json()
            print('result share link', result)

            if result.get('ResponseCode') == 1:
                return {
                    'success': True,
                    'data': result.get('Data', {}),
                    'message': result.get('ResponseMsg', 'Success')
                }
            else:
                return {
                    'success': False,
                    'message': result.get('ResponseMessage', 'API returned error')
                }

        except requests.exceptions.RequestException as e:
            _logger.error(f"API request failed: {str(e)}")
            return {'success': False, 'message': f'Request failed: {str(e)}'}
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error: {str(e)}")
            return {'success': False, 'message': 'Invalid response format'}
        except Exception as e:
            _logger.error(f"Unexpected error: {str(e)}")
            return {'success': False, 'message': f'Unexpected error: {str(e)}'}