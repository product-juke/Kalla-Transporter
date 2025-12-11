from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FleetLastCheckpointSyncWizard(models.TransientModel):
    _name = 'fleet.last.checkpoint.sync.wizard'
    _description = 'Wizard to Sync Fleet Last Checkpoint Data'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    @api.constrains('start_date', 'end_date')
    def _check_date_range(self):
        for rec in self:
            if rec.end_date < rec.start_date:
                raise ValidationError('End Date harus lebih besar atau sama dengan Start Date.')
            if (rec.end_date - rec.start_date).days > 7:
                raise ValidationError('Rentang tanggal maksimal 7 hari.')

    def action_sync_data(self):
        # Call the main model's sync function with the selected dates
        _logger.info(f"On sync last checkpoint data -> From {self.start_date} - To {self.end_date}")
        return self.env['fleet.last.checkpoint'].hit_endpoint_scheduler(
            called_from_ui=True, start_date=self.start_date, end_date=self.end_date
        )
