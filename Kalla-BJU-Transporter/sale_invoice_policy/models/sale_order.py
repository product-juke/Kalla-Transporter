# Copyright 2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    invoice_policy = fields.Selection(
        [("order", "CBD"), ("delivery", "TOP")],
        readonly=True,
        help="CBD: Cash Before Delivery.\n"
        "TOP: Term Of Payment. ",
    )
    invoice_policy_required = fields.Boolean(
        compute="_compute_invoice_policy_required",
        default=lambda self: self.env["ir.default"]._get(
            "res.config.settings", "sale_invoice_policy_required"
        ),
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        default_invoice_policy = (
            self.env["res.config.settings"]
            .sudo()
            .default_get(["default_invoice_policy"])
            .get("default_invoice_policy", False)
        )
        if "invoice_policy" not in res:
            res.update({"invoice_policy": default_invoice_policy})
        return res

    @api.depends("partner_id")
    def _compute_invoice_policy_required(self):
        invoice_policy_required = (
            self.env["res.config.settings"]
            .sudo()
            .default_get(["sale_invoice_policy_required"])
            .get("sale_invoice_policy_required", False)
        )
        for sale in self:
            sale.invoice_policy_required = invoice_policy_required

    # @api.depends('invoice_policy')
    # def _compute_invoice_status(self):
    #     super()._compute_invoice_status()
    #     for order in self:
    #         if all(line.invoice_status == 'invoiced' for line in order.order_line):
    #             order.invoice_status = 'invoiced'
    #         elif order.invoice_policy == 'order' and (order.delivery_status == 'pending' or not order.delivery_status):
    #             order.invoice_status = 'to invoice'
