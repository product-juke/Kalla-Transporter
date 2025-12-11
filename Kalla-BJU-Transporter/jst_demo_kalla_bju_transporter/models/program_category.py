# models/program_category.py
from odoo import models, fields, api


class ProgramCategory(models.Model):
    _name = 'program.category'
    _description = 'Program Category'
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        help='Program category name'
    )
    category_ids = fields.One2many('fleet.vehicle.model.category', 'program_category_id', ondelete='set null')

    # @api.model
    # def name_create(self, name):
    #     """Create a new record from name_create if it doesn't exist."""
    #     return self.create({'name': name}).name_get()[0]