from odoo import api, fields, models
import requests
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class FleetLastCheckpoint(models.Model):
    _inherit = 'fleet.last.checkpoint'

    def action_update_list_data(self):
        res = super(FleetLastCheckpoint, self).action_update_list_data()
        vehicles = res['vehicles']
        if vehicles and len(vehicles) > 0:
            for vehicle in vehicles:
                print('vehicle ', vehicle)
                query_update = """
                    UPDATE trx_vehicle_utilization
                    SET status_actual = 'UTILIZATION'
                    WHERE plate_no = %s AND vehicle_name = %s
                """
                self.env.cr.execute(query_update, (vehicle.license_plate, vehicle.name))
                self.env.cr.commit()
        return
