from odoo import fields, models, _


class AccountPaymentOracle(models.Model):
    _name = 'account.payment.oracle'
    _rec_name = 'name'

    name = fields.Char('Receipt Number', required=True)
    type = fields.Selection([('ar_top', 'AR TOP'),
                             ('ar_cbd', 'AR CBD'),
                             ('ap', 'AP')], default=False, required=True)
    status = fields.Selection([('not_paid', 'Not Paid'),
                               ('partial_paid', 'Partial'),
                               ('fully_paid', 'Fully Paid'),
                               ('nothing', 'Invoice Not Created')], default='not_paid')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Receipt Number must be unique!')
    ]
