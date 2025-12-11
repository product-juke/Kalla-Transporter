from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = ['account.move.line', 'portfolio.view.mixin']

    # category = fields.Many2one('fleet.vehicle.model.category', 'Vehicle Category')
    category = fields.Char()
    move_type = fields.Selection(
        selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
        ], related="move_id.move_type"
    )
    no_surat_jalan = fields.Char(readonly=True)
    tp_show_dpp_nilai_lain = fields.Boolean(compute="_compute_tp_show_dpp_nilai_lain")
    tp_dpp_nilai_lain = fields.Float('DPP Nilai Lain', compute="_compute_tp_dpp_nilai_lain")
    sodo_reference = fields.Char('SO-DO Reference')
    geofence_unloading = fields.Char("Geofence Unloading")
    is_for_journal_remaining_bop = fields.Boolean(default=False)

    @api.depends('tax_ids')
    def _compute_tp_show_dpp_nilai_lain(self):
        for rec in self:
            # Set default to False
            rec.tp_show_dpp_nilai_lain = False

            # Check if any tax has use_dpp_nilai_lain = True
            for tax in rec.tax_ids:
                if tax.use_dpp_nilai_lain:
                    rec.tp_show_dpp_nilai_lain = True
                    break  # No need to continue checking once we find one

    @api.depends('price_unit', 'quantity', 'price_subtotal', 'tp_show_dpp_nilai_lain')
    def _compute_tp_dpp_nilai_lain(self):
        for rec in self:
            if rec.tp_show_dpp_nilai_lain:
                rec.tp_dpp_nilai_lain = rec.price_subtotal * 11 / 12
            else:
                rec.tp_dpp_nilai_lain = 0

    @api.model
    def get_dashboard_data(self):
        """Fetch dashboard data for Revenue, Expenses, Outstanding Payments, Aging Report, etc."""
        revenue = sum(self.env["account.move.line"].search([("account_id.account_type", "=", "income")]).mapped("balance"))
        expenses = sum(self.env["account.move.line"].search([("account_id.account_type", "=", "expense")]).mapped("balance"))

        # Get outstanding payments
        outstanding_payments = sum(self.env["account.move.line"].search([
            ("account_id.account_type", "in", ["asset_receivable", "liability_payable"]),
            ("reconciled", "=", False),
        ]).mapped("balance"))

        # Get aging report
        aging_buckets = {
            "0-30": 0,
            "31-60": 0,
            "61-90": 0,
            "90+": 0,
        }
        today = fields.Date.today()
        lines = self.env["account.move.line"].search([
            ("account_id.account_type", "=", "asset_receivable"),
            ("reconciled", "=", False),
        ])
        for line in lines:
            days_due = (today - line.date_maturity).days if line.date_maturity else 0
            if days_due <= 30:
                aging_buckets["0-30"] += line.balance
            elif days_due <= 60:
                aging_buckets["31-60"] += line.balance
            elif days_due <= 90:
                aging_buckets["61-90"] += line.balance
            else:
                aging_buckets["90+"] += line.balance

        # Get cash flow (inflow & outflow)
        cash_in = sum(self.env["account.move.line"].search([("credit", ">", 0)]).mapped("credit"))
        cash_out = sum(self.env["account.move.line"].search([("debit", ">", 0)]).mapped("debit"))

        # Get tax collected
        total_tax_collected = sum(self.env["account.move.line"].search([("tax_line_id", "!=", False)]).mapped("balance"))

        # Get profitability (Revenue - Expenses)
        profitability = revenue - abs(expenses)

        return {
            "revenue": revenue,
            "expenses": abs(expenses),
            "outstandingPayments": outstanding_payments,
            "agingReport": aging_buckets,
            "cashFlowIn": cash_in,
            "cashFlowOut": cash_out,
            "totalTaxCollected": total_tax_collected,
            "profitability": profitability,
        }
        
    # @api.model_create_multi
    # def create(self, vals_list):
    #     if self.env.company.portfolio_id.name != 'Frozen':
    #         for vals in vals_list:
    #             _logger.info(f"on running...")
    #             if vals.get('display_type') == 'product':
    #                 _logger.info(f"display_type -> {vals.get('display_type')}")
    #                 _logger.info(f"display_type -> {vals.get('account_id')}")
    #                 if not vals.get('account_id'):
    #                     expense_account = self.env['account.account'].search([
    #                         ('account_type', '=', 'asset_prepayments'),
    #                         ('code', '=', '11410040'),
    #                     ], limit=1)
                        
    #                     if not expense_account:
    #                         raise ValidationError(_("Akun expense (11410040) tidak ditemukan."))

    #                     vals['account_id'] = expense_account.id
                    
    #     return super().create(vals_list)
