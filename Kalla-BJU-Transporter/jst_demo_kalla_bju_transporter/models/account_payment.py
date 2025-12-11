from odoo import models, fields, api, _
import pprint


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        res = super(AccountPayment, self).action_post()

        for rec in self:
            payment_invoice = self.env['account.move'].search([
                ('id', '=', rec.move_id.id),
            ])
            if payment_invoice:
                customer_invoices = self.env['account.move'].search([
                    ('name', 'in', str(payment_invoice.ref).split(',')),
                    ('move_type', '=', 'out_invoice'),
                ])
                combined_distribution = {}
                for move in customer_invoices:
                    for line in move.invoice_line_ids:
                        if line.analytic_distribution:
                            combined_distribution.update(line.analytic_distribution)

                if combined_distribution:
                    for item in payment_invoice.line_ids:
                        item.sudo().write({
                            'analytic_distribution': combined_distribution
                        })
        return res

    def _create_paired_internal_transfer_payment(self):
        res = super(AccountPayment, self)._create_paired_internal_transfer_payment()
        return res