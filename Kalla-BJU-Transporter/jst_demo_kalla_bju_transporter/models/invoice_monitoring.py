from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class InvoiceMonitoring(models.Model):
    _name = 'invoice.monitoring'
    _description = 'Invoice Monitoring Statistics'

    @api.model
    def get_sale_order_views(self):
        tree_view = self.env.ref("jst_demo_kalla_bju_transporter.transporter_sale_order_tree").id
        form_view = self.env.ref("jst_demo_kalla_bju_transporter.transporter_sale_order_form").id
        return {
            "tree": tree_view,
            "form": form_view,
        }

    @api.model
    def _get_base_invoice_domain(self, allowed_company_ids):
        """Get base domain for invoices"""
        return [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', 'in', allowed_company_ids)
        ]

    @api.model
    def _get_base_sale_order_domain(self, allowed_company_ids):
        """Get base domain for sale orders"""
        return [
            ('company_id', 'in', allowed_company_ids)
        ]

    @api.model
    def get_invoice_statistics(self, allowed_company_ids=None):
        """Get invoice statistics for dashboard cards"""
        try:
            _logger.info("Getting invoice statistics...")

            if not allowed_company_ids:
                allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])

            _logger.info(f"Allowed companies: {allowed_company_ids}")

            # Base domains
            base_invoice_domain = self._get_base_invoice_domain(allowed_company_ids)
            base_so_domain = self._get_base_sale_order_domain(allowed_company_ids)

            view_ids = self.get_sale_order_views()

            stats = {
                'done_not_invoiced': 0,
                'draft_invoices': 0,
                'done_not_paid': 0,
                'done_not_sent': 0,
                'paid_invoices': 0,
                'view_ids': view_ids,
            }

            # Count draft invoices - SAMA dengan filter di JS
            draft_domain = base_invoice_domain + [('state', '=', 'draft')]
            stats['draft_invoices'] = self.env['account.move'].search_count(draft_domain)
            _logger.info(f"Draft invoices: {stats['draft_invoices']}")

            # Count posted invoices that are not paid - SAMA dengan filter di JS
            done_not_paid_domain = base_invoice_domain + [
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial'])
            ]
            stats['done_not_paid'] = self.env['account.move'].search_count(done_not_paid_domain)
            _logger.info(f"Done not paid: {stats['done_not_paid']}")

            # Count posted invoices that are not sent - DIPERBAIKI agar sama dengan JS
            # Di JS menggunakan date_sent_to_customer, bukan is_move_sent
            done_not_sent_domain = base_invoice_domain + [
                ('state', '=', 'posted'),
                ('date_sent_to_customer', '=', False)  # Ubah dari is_move_sent ke date_sent_to_customer
            ]
            stats['done_not_sent'] = self.env['account.move'].search_count(done_not_sent_domain)
            _logger.info(f"Done not sent: {stats['done_not_sent']}")

            # Count paid invoices - SAMA dengan filter di JS
            paid_domain = base_invoice_domain + [
                ('state', '=', 'posted'),
                ('payment_state', '=', 'paid')
            ]
            stats['paid_invoices'] = self.env['account.move'].search_count(paid_domain)
            _logger.info(f"Paid invoices: {stats['paid_invoices']}")

            # Count doc delivery - SAMA dengan filter di JS
            doc_delivery_domain = [
                ('vehicle_id', '!=', False),
                ('status_do', '=', 'DO Match'),
                ('state', '=', 'approved_by_kacab'),
                ('company_id', 'in', allowed_company_ids)
            ]
            stats['doc_delivery'] = self.env['fleet.do'].search_count(doc_delivery_domain)
            _logger.info(f"Doc Delivery: {stats['doc_delivery']}")

            # Count sales orders that are done but not invoiced - SAMA dengan filter di JS
            if 'sale.order' in self.env:
                done_not_invoiced_domain = base_so_domain + [
                    ('state', '=', 'sale'),
                    ('invoice_status', 'in', ['to invoice'])
                ]
                stats['done_not_invoiced'] = self.env['sale.order'].search_count(done_not_invoiced_domain)
            _logger.info(f"Done not invoiced: {stats['done_not_invoiced']}")

            _logger.info(f"Final stats: {stats}")
            return stats

        except Exception as e:
            _logger.error(f"Error getting invoice statistics: {str(e)}")
            return {
                'done_not_invoiced': 0,
                'draft_invoices': 0,
                'done_not_paid': 0,
                'done_not_sent': 0,
                'paid_invoices': 0,
                'doc_delivery': 0,
                'view_ids': {},
            }

    @api.model
    def get_invoice_details(self, filter_type, allowed_company_ids=None):
        """Get detailed invoice data based on filter type"""
        try:
            _logger.info(f"Getting invoice data for filter: {filter_type}")

            if not allowed_company_ids:
                allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])

            _logger.info(f"Allowed companies: {allowed_company_ids}")

            # Base domains
            base_invoice_domain = self._get_base_invoice_domain(allowed_company_ids)
            base_so_domain = self._get_base_sale_order_domain(allowed_company_ids)

            if filter_type == 'draft_invoices':
                domain = base_invoice_domain + [('state', '=', 'draft')]

            elif filter_type == 'done_not_paid':
                domain = base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ]

            elif filter_type == 'done_not_sent':
                # DIPERBAIKI - gunakan date_sent_to_customer seperti di JS
                domain = base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('date_sent_to_customer', '=', False)  # Sama dengan JS
                ]

            elif filter_type == 'paid_invoices':
                domain = base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('payment_state', '=', 'paid')
                ]

            if filter_type == 'done_not_invoiced':
                # For sales orders - SAMA dengan filter di JS
                if 'sale.order' not in self.env:
                    return []

                domain = base_so_domain + [
                    ('state', '=', 'sale'),
                    ('invoice_status', 'in', ['to invoice', 'no'])
                ]
                orders = self.env['sale.order'].search(domain, limit=100)
                return [{
                    'id': order.id,
                    'name': order.name,
                    'partner_name': order.partner_id.name if order.partner_id else 'N/A',
                    'amount_total': order.amount_total,
                    'date_order': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
                    'state': order.state,
                    'invoice_status': order.invoice_status,
                    'company_name': order.company_id.name if order.company_id else 'N/A',
                } for order in orders]
            else:
                # For invoices
                invoices = self.env['account.move'].search(domain, limit=100)
                return [{
                    'id': invoice.id,
                    'name': invoice.name or 'N/A',
                    'partner_name': invoice.partner_id.name if invoice.partner_id else 'N/A',
                    'amount_total': invoice.amount_total,
                    'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                    'state': invoice.state,
                    'payment_state': invoice.payment_state,
                    'date_sent_to_customer': invoice.date_sent_to_customer.strftime(
                        '%Y-%m-%d') if invoice.date_sent_to_customer else '',
                    'company_name': invoice.company_id.name if invoice.company_id else 'N/A',
                } for invoice in invoices]

        except Exception as e:
            _logger.error(f"Error getting invoice data for {filter_type}: {str(e)}")
            return []

    @api.model
    def get_synchronized_data(self, allowed_company_ids=None):
        """Get both statistics and domain filters to ensure synchronization"""
        try:
            if not allowed_company_ids:
                allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])

            # Get statistics
            stats = self.get_invoice_statistics(allowed_company_ids)

            # Return both stats and domains for verification
            base_invoice_domain = self._get_base_invoice_domain(allowed_company_ids)
            base_so_domain = self._get_base_sale_order_domain(allowed_company_ids)

            domains = {
                'draft_invoices': base_invoice_domain + [('state', '=', 'draft')],
                'done_not_paid': base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ],
                'done_not_sent': base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('date_sent_to_customer', '=', False)
                ],
                'paid_invoices': base_invoice_domain + [
                    ('state', '=', 'posted'),
                    ('payment_state', '=', 'paid')
                ],
                'done_not_invoiced': base_so_domain + [
                    ('state', '=', 'sale'),
                    ('invoice_status', 'in', ['to invoice', 'no'])
                ]
            }

            return {
                'stats': stats,
                'domains': domains,
                'allowed_company_ids': allowed_company_ids
            }

        except Exception as e:
            _logger.error(f"Error getting synchronized data: {str(e)}")
            return {
                'stats': {
                    'done_not_invoiced': 0,
                    'draft_invoices': 0,
                    'done_not_paid': 0,
                    'done_not_sent': 0,
                    'paid_invoices': 0,
                },
                'domains': {},
                'allowed_company_ids': allowed_company_ids or []
            }