from odoo import fields, models, api



class FleetVehicleModelCategory(models.Model):
    _inherit = 'fleet.vehicle.model.category'

    product_category_id = fields.Many2one('product.category',
                                          domain=[('name', 'in', ['Transporter', 'VLI', 'Trucking'])], string="Business Category",required=True)
    program_category_id = fields.Many2one('program.category', string="Program")
    min_tonase = fields.Float('Minimum Tonase')
    max_tonase = fields.Float('Maximum Tonase')
    min_kubikasi = fields.Float('Minimum Kubikasi')
    max_kubikasi = fields.Float('Maximum Kubikasi')
    max_unit = fields.Float('Maximum Unit')
    is_shipment = fields.Boolean('Shipment Category')
    optional_products = fields.Boolean('Optional Products')