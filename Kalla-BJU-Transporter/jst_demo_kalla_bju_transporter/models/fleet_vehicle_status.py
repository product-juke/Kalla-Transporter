from odoo import fields, models, api, _

class FleetVehicleStatus(models.Model):

    _name = 'fleet.vehicle.status'
    _rec_name = 'name_description'

    vehicle_status = fields.Selection([('ready', 'Ready'), ('on_going', 'On Going'),('on_return','On Return'),('not_ready','Not Ready')],
                                     'Last Status')
    name_description = fields.Char(string='Last Status Description')