# -*- coding: utf-8 -*-
# from odoo import http


# class JstFleetMonitorUnit(http.Controller):
#     @http.route('/jst_fleet_monitor_unit/jst_fleet_monitor_unit', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/jst_fleet_monitor_unit/jst_fleet_monitor_unit/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('jst_fleet_monitor_unit.listing', {
#             'root': '/jst_fleet_monitor_unit/jst_fleet_monitor_unit',
#             'objects': http.request.env['jst_fleet_monitor_unit.jst_fleet_monitor_unit'].search([]),
#         })

#     @http.route('/jst_fleet_monitor_unit/jst_fleet_monitor_unit/objects/<model("jst_fleet_monitor_unit.jst_fleet_monitor_unit"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('jst_fleet_monitor_unit.object', {
#             'object': obj
#         })

