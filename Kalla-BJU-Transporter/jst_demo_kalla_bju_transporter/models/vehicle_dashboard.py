from odoo import models, fields, api, http
from odoo.http import request

class VehicleDashboard(models.Model):
    _name = 'vehicle.dashboard'
    _description = 'Vehicle Dashboard'

    total_dos = fields.Integer(string="Total Delivery Orders", compute="_compute_total_do")
    pending_dos = fields.Integer(string="Pending Deliver Orders", compute="_compute_pending_do")
    done_dos = fields.Integer(string="Done Deliver Orders", compute="_compute_done_do")
    vehicle_count_ready = fields.Integer(string="Vehicle Ready for Use", compute="_compute_vehicle_ready")
    vehicle_count_ready_on_book = fields.Integer(string="Vehicle Ready On Book", compute="_compute_vehicle_on_book")

    @api.depends('total_do')
    def _compute_total_orders(self):
        SaleOrder = self.env['fleet.do']
        self.total_dos = SaleOrder.search_count([])

    @api.depends('pending_dos')
    def _compute_pending_dos(self):
        SaleOrder = self.env['fleet.do']
        self.pending_dos = SaleOrder.search_count([('state', '=', 'draft')])

    @api.depends('done_dos')
    def _compute_done_dos(self):
        SaleOrder = self.env['fleet.do']
        self.done_dos = SaleOrder.search_count([('state', '=', 'done'),('status_do', '=', 'DO Match')])

    @api.depends('vehicle_count_ready')
    def _compute_vehicle_ready(self):
        FleetVehicle = self.env['fleet.vehicle']
        self.vehicle_count_ready = FleetVehicle.search_count([('vehicle_status', '=', 'ready'),('last_status_description_id', '=', 1)])

    @api.depends('vehicle_count_ready_on_book')
    def _compute_vehicle_ready(self):
        FleetVehicle = self.env['fleet.vehicle']
        self.vehicle_count_ready_on_book = FleetVehicle.search_count([('vehicle_status', '=', 'ready'),('last_status_description_id', '=', 2)])
