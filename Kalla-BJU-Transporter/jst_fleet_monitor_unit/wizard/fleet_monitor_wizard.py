from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class FleetMonitorWizard(models.TransientModel):
    _name = 'fleet.monitor.wizard'
    _description = 'Fleet Monitor Unit Wizard'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True)
    duration_hours = fields.Integer(
        string='Duration (Hours)',
        required=True,
        default=1,
        help='Enter duration between 1-24 hours'
    )
    api_token = fields.Char(
        string='API Token',
        # required=True,
        help='Enter your EasyGo GPS API Token'
    )

    @api.constrains('duration_hours')
    def _check_duration_hours(self):
        for record in self:
            if record.duration_hours < 1 or record.duration_hours > 24:
                raise UserError('Duration must be between 1 and 24 hours.')

    def action_create_monitor_link(self):
        """Create monitor link and open in new tab"""
        if not self.vehicle_id:
            raise UserError('Vehicle is required')

        # if not self.api_token:
        #     raise UserError('API Token is required')

        # Create share link
        result = self.vehicle_id.create_share_link(self.duration_hours, '55AEED3BF70241F8BD95EAB1DB2DEF67')

        if not result['success']:
            raise UserError(f"Failed to create share link: {result['message']}")

        # Extract URL from response data
        share_data = result['data']
        if isinstance(share_data, dict) and 'url' in share_data:
            share_url = share_data['url']
        elif isinstance(share_data, dict) and 'link' in share_data:
            share_url = share_data['link']
        elif isinstance(share_data, str):
            share_url = share_data
        else:
            raise UserError('No valid URL found in API response')

        # Open URL in new tab
        return {
            'type': 'ir.actions.act_url',
            'url': share_url,
            'target': 'new',
        }