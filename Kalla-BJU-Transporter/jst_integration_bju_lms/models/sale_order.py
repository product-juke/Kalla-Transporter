from odoo import fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portfolio.view.mixin']

    oracle_number = fields.Char(copy=False, tracking=True)
    failed_payment_ar_cbd = fields.Boolean('Failed Payment AR CBD', copy=False, tracking=True)


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        res = super(SaleAdvancePaymentInv, self).create_invoices()
        for order in self.sale_order_ids:
            for invoice in order.invoice_ids:
                if order.invoice_policy == 'order':
                    invoice.oracle_number = order.oracle_number
        return res