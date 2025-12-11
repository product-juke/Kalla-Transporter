from odoo import models, fields, api, _

BRANCH = [
    ('lmks', "LMKS"),
    ('ljkt', "LJKT"),
    ('vli', "VLI"),
    ('clm', "CLM"),
    ('bpp', "BPP"),
    ('sby1', "SBY1"),
    ('bpp1', "BPP1"),
    ('mks1', "MKS1"),
    ('mks2', "MKS2"),
    ('lwu', "LWU"),
    ('cabo', "CABO"),
]

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    branch = fields.Selection(selection=BRANCH, default=False)