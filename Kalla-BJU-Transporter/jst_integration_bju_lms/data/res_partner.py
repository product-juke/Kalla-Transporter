from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def ir_cron_action_retry_create_customer(self):
        customers = self.env['res.partner'].search([('oracle_sync_date', '!=', False),
                                                    ('oracle_sync_statusCode', '!=', 202),
                                                    ('oracle_sync_message', '!=', 'Accepted')])
        if customers:
            for customer in customers:
                customer.with_delay().send_customer(customer)
