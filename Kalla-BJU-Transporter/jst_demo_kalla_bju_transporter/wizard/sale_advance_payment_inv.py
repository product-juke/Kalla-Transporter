# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)


class SaleAdvancePaymentInv(models.TransientModel):
    _name = 'sale.advance.payment.inv'
    _inherit = ['sale.advance.payment.inv', 'portfolio.view.mixin']


    def _create_invoices(self, sale_orders):
        """
        Override to adjust price_unit before invoice creation.
        Instead of creating new records, we temporarily modify the order lines.
        """
        if self.is_fms(self.env.company.portfolio_id.name):
            return super()._create_invoices(sale_orders)

        # Store original price_unit values to restore later
        original_prices = {}

        try:
            # Temporarily modify price_unit for lines with actual_price_unit
            for order in sale_orders:
                for line in order.order_line:
                    actual_price_unit = line.actual_price_unit
                    if actual_price_unit and actual_price_unit > 0:
                        # Store original price
                        original_prices[line.id] = line.price_unit
                        # Temporarily update price_unit
                        line.price_unit = actual_price_unit

                        if line and actual_price_unit:
                            total_price_unit = actual_price_unit
                            if str(line.order_id.invoiced_by) == 'volume':
                                total_price_unit = line.actual_volume * actual_price_unit
                            elif str(line.order_id.invoiced_by) == 'tonase':
                                total_price_unit = line.actual_tonase * actual_price_unit

                            if not line.order_id.partner_id.is_tam and len(line.order_id.sale_order_option_ids) > 0:
                                total_price_unit = actual_price_unit

                            line.price_unit = total_price_unit

                        _logger.info(f'Check partner is TAM => {order.partner_id.is_tam}')
                        if order.partner_id.is_tam:
                            _logger.info(f'Processing Invoice Total for TAM Customer => {order.total_actual_price}')
                            line.price_unit = order.total_actual_price

            # Call parent method with modified orders
            result = super()._create_invoices(sale_orders)

            return result

        finally:
            if self.is_lms(self.env.company.portfolio_id.name):
                # Restore original prices
                for line_id, original_price in original_prices.items():
                    line = self.env['sale.order.line'].browse(line_id)
                    if line.exists():
                        line.price_unit = original_price

    def create_invoices(self):

        for wizard in self:
            # Ambil sale order dari context
            order_ids = self.env.context.get('active_ids', [])
            orders = self.env['sale.order'].browse(order_ids)

            # VALIDASI AWAL: Pastikan semua Sales Order memiliki Customer yang sama
            if len(orders) > 1:
                customers = orders.mapped('partner_id')
                if len(customers) > 1:
                    customer_names = ', '.join(customers.mapped('name'))
                    raise UserError(
                        f"Tidak dapat membuat invoice untuk Sales Order dengan Customer yang berbeda.\n"
                        f"Customer yang ditemukan: {customer_names}\n"
                        f"Silakan pilih Sales Order dengan Customer yang sama."
                    )

            if wizard.env.company.portfolio_id.name != 'Frozen':
                for order in orders:

                    # header_lines = order.order_line.filtered(lambda l: l.is_header and l.do_id)
                    # if not header_lines:
                    #     raise UserError("Tidak ada DO header yang ditemukan.")
                    # for line in header_lines:

                    do_ids = order.order_line.mapped('do_id').filtered(lambda d: d)  # skip None
                    if not do_ids:
                        raise UserError("Tidak ada Delivery Order terkait pada Sales Order ini.")

                    for do in do_ids:
                        if do.vehicle_id.asset_type == 'asset':
                            do_nominal = float_round(do.nominal, precision_digits=0, rounding_method='UP')
                            do_bop_paid = float_round(do.bop_paid, precision_digits=0, rounding_method='UP')
                            
                            if do_bop_paid != do_nominal:
                                raise UserError(
                                    f"BOP yang dibayarkan belum 100% pada DO {do.name}.")
                            
                            for bop in do.bop_ids:
                                bop_no = bop.bop_no
                                if not bop_no:
                                    continue

                                vendor_bill = self.env['account.move'].search([
                                    ('move_type', '=', 'in_invoice'),
                                    ('ref', 'ilike', bop_no)
                                ], limit=1)

                                if not vendor_bill:
                                    raise UserError(
                                        f"BOP {bop_no} belum dibuat Vendor Bill."
                                    )

                                if vendor_bill.state != 'posted':
                                    raise UserError(
                                        f"BOP {bop_no} sudah dibuat Vendor Bill ({vendor_bill.name}) tapi belum posted."
                                    )

        """
        Override metode create_invoices pada wizard untuk menambahkan kategori pada Move Line
        """
        result = super(SaleAdvancePaymentInv, self).create_invoices()

        move_id = result.get('res_id')
        move = self.env['account.move'].search([('id', '=', move_id)], limit=1)

        if self.env.company.portfolio_id.name != 'Frozen':
            orders = self.env['sale.order'].search([
                ('name', 'in', move.invoice_origin.split(', '))
            ])

            for order in orders:
                no_surat_jalan_list = order.order_line._collect_no_surat_jalan()
                filtered_order_line = order.order_line.filtered(lambda r: r.no_surat_jalan and r.do_id)

                for order_line in filtered_order_line:
                    filtered_order_line._update_related_records(order_line, no_surat_jalan_list)

        if self.env.company.portfolio_id.name != 'Frozen':
            receivable_account = self.env['account.move.line'].search([
                ('move_id', '=', move_id),
                ('account_id.code', '=', '11210010'),
                ('account_id.name', '=', 'Account Receivable'),
            ], limit=1)
            sales_accounts = self.env['account.move.line'].search([
                ('move_id', '=', move_id),
                ('account_id.code', '=', '41000010'),
                ('account_id.name', '=', 'Sales'),
            ])

            combined_distribution = {}
            for sales_line in sales_accounts:
                if sales_line.analytic_distribution:
                    combined_distribution.update(sales_line.analytic_distribution)

            # Update receivable account dengan gabungan analytic distribution
            if combined_distribution:
                receivable_account.sudo().write({
                    'analytic_distribution': combined_distribution
                })

        default_invoice_origin = None

        # Fix: Use .get() method to safely access nested dictionary keys
        if result and result.get('context') and result.get('context', {}).get('default_invoice_origin'):
            default_invoice_origin = result['context']['default_invoice_origin']

        if default_invoice_origin:
            order = self.env['sale.order'].search([('name', '=', default_invoice_origin)], limit=1)
            move = self.env['account.move'].search([('id', '=', move_id)], limit=1)
            print('order', order, move, len(move.invoice_line_ids), len(move.line_ids))
            if move and order and order.product_category_id:
                for line in move.line_ids:
                    if line.product_id.vehicle_category_id:
                        self.env.cr.execute(
                            """
                            UPDATE account_move_line
                            SET category = %s
                            WHERE id = %s
                            """,
                            (line.product_id.vehicle_category_id.id, line.id)
                        )

            if self.is_lms(self.env.company.portfolio_id.name):
                if move.partner_id:
                    partner = move.partner_id
                    move.invoice_line_ids.write({
                        'tax_ids': partner.partner_tax_ids
                    })
                    if partner.tax_invoicing_method == 'total_invoice':
                        move.tax_ids = partner.partner_tax_ids

                _logger.info(f"On Create Invoice => ({len(move.invoice_line_ids)}) -> {move.invoice_line_ids}")
                if move.invoice_line_ids:
                    for line in move.invoice_line_ids:
                        _logger.info(f"On Create Invoice => Line ID: ({line.id}) -> {line}")
                        query = """
                            SELECT invoice_line_id, order_line_id FROM sale_order_line_invoice_rel solir
                            WHERE solir.invoice_line_id = %s
                            LIMIT 1
                        """
                        self.env.cr.execute(query, (line.id,))
                        result = self.env.cr.dictfetchone()

                        _logger.info(f'On Create Invoice => Query Result -> {result}')

                        if result and 'order_line_id' in result:
                            order_line = self.env['sale.order.line'].search([
                                ('id', '=', result['order_line_id']),
                            ], limit=1)

                            _logger.info(f'On Create Invoice => Order Line -> {order_line}')

                            actual_price_unit = order_line.actual_price_unit
                            if order_line and actual_price_unit:
                                total_price_unit = actual_price_unit
                                if str(order_line.order_id.invoiced_by) == 'volume':
                                    total_price_unit = order_line.actual_volume * actual_price_unit
                                elif str(order_line.order_id.invoiced_by) == 'tonase':
                                    total_price_unit = order_line.actual_volume * actual_price_unit

                                if not order_line.order_id.partner_id.is_tam and len(order_line.order_id.sale_order_option_ids) > 0:
                                    total_price_unit = actual_price_unit

                                _logger.info(f'Check partner is TAM After Invoice is created => {order_line.order_id.partner_id.is_tam}')
                                if order_line.order_id.partner_id.is_tam:
                                    _logger.info(f'Processing Invoice Total for TAM Customer After Invoice is created => {order.total_actual_price}')
                                    total_price_unit = order_line.order_id.total_actual_price

                                self.env.cr.execute(
                                    """
                                    UPDATE account_move_line
                                    SET price_unit = %s
                                    WHERE id = %s
                                    """,
                                    (total_price_unit, line.id)
                                )

        return result