from odoo import models, fields, api

class AccountingDashboard(models.Model):
    _name = 'accounting.dashboard'
    _description = 'Accounting Dashboard Data'

    @api.model
    def get_dashboard_data(self):
        # Revenue & Expenses (Credit = Revenue, Debit = Expenses)
        revenue = sum(self.env['account.move.line'].search([
            ('account_id.user_type_id.name', '=', 'Receivable'),
            ('move_id.state', '=', 'posted')
        ]).mapped('credit'))

        expenses = sum(self.env['account.move.line'].search([
            ('account_id.user_type_id.name', '=', 'Payable'),
            ('move_id.state', '=', 'posted')
        ]).mapped('debit'))

        # Outstanding Payments (Unpaid Invoices)
        outstanding_payments = sum(self.env['account.move'].search([
            ('payment_state', '=', 'not_paid'),
            ('move_type', '=', 'out_invoice')
        ]).mapped('amount_total'))

        # Aging Report (Invoices grouped by overdue days)
        aging_report = {
            '0-30': 0, '31-60': 0, '61-90': 0, '90+': 0
        }
        today = fields.Date.today()
        for invoice in self.env['account.move'].search([('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]):
            days_overdue = (today - invoice.invoice_date_due).days if invoice.invoice_date_due else 0
            if days_overdue <= 30:
                aging_report['0-30'] += invoice.amount_total
            elif days_overdue <= 60:
                aging_report['31-60'] += invoice.amount_total
            elif days_overdue <= 90:
                aging_report['61-90'] += invoice.amount_total
            else:
                aging_report['90+'] += invoice.amount_total

        # Cash Flow (Payments in and out)
        cash_flow_in = sum(self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'), ('state', '=', 'posted')
        ]).mapped('amount'))

        cash_flow_out = sum(self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'), ('state', '=', 'posted')
        ]).mapped('amount'))

        # Tax Reports
        total_tax_collected = sum(self.env['account.move.line'].search([
            ('tax_line_id', '!=', False), ('move_id.state', '=', 'posted')
        ]).mapped('tax_line_id.amount'))

        # Profitability
        profitability = revenue - expenses

        return {
            'revenue': revenue,
            'expenses': expenses,
            'outstanding_payments': outstanding_payments,
            'aging_report': aging_report,
            'cash_flow_in': cash_flow_in,
            'cash_flow_out': cash_flow_out,
            'total_tax_collected': total_tax_collected,
            'profitability': profitability
        }
