from odoo import models, fields, api, _
import logging


_logger = logging.getLogger(__name__)

class SupplierProductService(models.Model):
    _name = 'supplier.product.service'

    product_service_category_id = fields.Char()
    category_name = fields.Char()
    category_type = fields.Char()
    is_active = fields.Boolean(default=False)
