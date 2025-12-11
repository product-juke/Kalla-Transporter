from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.addons.account.wizard.account_payment_register import AccountPaymentRegister as APR


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'portfolio.view.mixin']

    CASH_RECEIPT_ID = fields.Char()
    CHECK_ID = fields.Char()
    RECEIPT_NUMBER = fields.Char()

    def _get_combined_analytic_distribution(self):
        """Get combined analytic distribution from reconciled invoices"""
        combined_distribution = {}

        # Get reconciled invoices
        reconciled_moves = self._get_reconciled_invoices()

        for reconciled_move in reconciled_moves:
            for line in reconciled_move.invoice_line_ids:  # Menggunakan invoice_line_ids yang benar
                if line.analytic_distribution:
                    combined_distribution.update(line.analytic_distribution)

        return combined_distribution

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        '''Override to create separate move lines per Sales Order and apply analytic distribution'''
        self.ensure_one()

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Get combined analytic distribution from invoices
        combined_distribution = {}
        if self.is_lms(self.env.company.portfolio_id.name):
            combined_distribution = self._get_combined_analytic_distribution()
            print('Combined analytic distribution:', combined_distribution)

        # Check if we need SO separation
        print('_should_separate_by_so():', self._should_separate_by_so())
        if not self._should_separate_by_so():
            # Use standard method but apply analytic distribution
            line_vals_list = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance)

            # Apply combined analytic distribution to all lines if available
            if combined_distribution:
                for line_vals in line_vals_list:
                    if line_vals.get('account_id'):  # Only apply to actual accounting lines
                        line_vals['analytic_distribution'] = combined_distribution

            return line_vals_list

        return self._prepare_move_lines_by_so(write_off_line_vals, force_balance, combined_distribution)

    def _should_separate_by_so(self):
        '''Determine if payment should be separated by Sales Orders'''
        # Only separate if payment is reconciling multiple invoices from different SOs
        so_groups = self._get_so_groups()
        print('so_groups', so_groups)
        return len(so_groups) > 0

    def _get_so_groups(self):
        '''Group reconciled invoices by Sales Order - Improved version'''
        so_groups = {}

        # Get reconciled invoices from this payment
        reconciled_moves = self._get_reconciled_invoices()
        print(f"Found {len(reconciled_moves)} reconciled invoices")

        for move in reconciled_moves:
            print(f"\nProcessing invoice: {move.name}")
            so_id = self._get_so_from_invoice(move)
            so_key = str(so_id) if so_id else 'no_so'

            if so_key not in so_groups:
                so_groups[so_key] = {
                    'invoices': [],
                    'total_amount': 0.0,
                    'so_record': None
                }

            # Use the correct amount field
            if move.currency_id and move.currency_id != move.company_currency_id:
                amount = abs(move.amount_residual_currency)
            else:
                amount = abs(move.amount_residual)

            so_groups[so_key]['invoices'].append(move)
            so_groups[so_key]['total_amount'] += amount

            if so_id:
                if not so_groups[so_key]['so_record']:
                    so_groups[so_key]['so_record'] = self.env['sale.order'].browse(so_id)
                print(f"  Assigned to SO: {so_groups[so_key]['so_record'].name}")
            else:
                print(f"  No SO found for invoice {move.name}")

        print(f"Final SO groups: {list(so_groups.keys())}")
        return so_groups

    def _get_reconciled_invoices(self):
        '''Get invoices that will be reconciled with this payment - Improved version'''
        invoices = self.env['account.move']

        print("Getting reconciled invoices...")

        # Method 1: From reconciled_invoice_ids if available
        if hasattr(self, 'reconciled_invoice_ids') and self.reconciled_invoice_ids:
            invoices = self.reconciled_invoice_ids.mapped('move_id')
            print(f"  Found {len(invoices)} from reconciled_invoice_ids")

        # Method 2: From reconciled_statement_line_ids
        elif hasattr(self, 'reconciled_statement_line_ids') and self.reconciled_statement_line_ids:
            for line in self.reconciled_statement_line_ids:
                if line.move_id and line.move_id.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
                    invoices |= line.move_id
            print(f"  Found {len(invoices)} from reconciled_statement_line_ids")

        # Method 3: Find from payment context if available
        elif self._context.get('active_model') == 'account.move' and self._context.get('active_ids'):
            invoice_ids = self._context.get('active_ids', [])
            invoices = self.env['account.move'].browse(invoice_ids).filtered(
                lambda m: m.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
            print(f"  Found {len(invoices)} from context active_ids")

        # Method 4: From payment register wizard context
        elif self._context.get('active_model') == 'account.move.line' and self._context.get('active_ids'):
            line_ids = self._context.get('active_ids', [])
            move_lines = self.env['account.move.line'].browse(line_ids)
            invoices = move_lines.mapped('move_id').filtered(
                lambda m: m.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
            print(f"  Found {len(invoices)} from context move lines")

        # Method 5: Try to get from reconciliation records if this is called during reconciliation
        if not invoices and hasattr(self, 'move_id') and self.move_id:
            # Get invoices that will be reconciled with this payment's move lines
            payment_lines = self.move_id.line_ids.filtered(lambda l: l.account_id.reconcile)
            for line in payment_lines:
                # Look for matching account receivable/payable lines
                domain = [
                    ('account_id', '=', line.account_id.id),
                    ('partner_id', '=', line.partner_id.id),
                    ('reconciled', '=', False),
                    ('amount_residual', '!=', 0),
                    ('move_id.move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
                ]
                potential_lines = self.env['account.move.line'].search(domain)
                invoices |= potential_lines.mapped('move_id')
            print(f"  Found {len(invoices)} from reconciliation analysis")

        # Method 6: From payment register context - additional check
        if not invoices and self.env.context.get('default_line_ids'):
            line_ids = self.env.context.get('default_line_ids')
            if isinstance(line_ids, list) and line_ids and isinstance(line_ids[0], tuple):
                # Extract IDs from One2many format [(6, 0, [ids])]
                if line_ids[0][0] == 6:
                    actual_line_ids = line_ids[0][2]
                    move_lines = self.env['account.move.line'].browse(actual_line_ids)
                    invoices = move_lines.mapped('move_id').filtered(
                        lambda m: m.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
                    print(f"  Found {len(invoices)} from default_line_ids")

        print(f"Total reconciled invoices: {len(invoices)}")
        for inv in invoices:
            print(f"  - {inv.name} ({inv.move_type})")

        return invoices

    def _get_so_from_invoice(self, invoice):
        '''Extract Sales Order ID from invoice - Improved version'''
        so_id = None

        print(f"Debugging invoice {invoice.name}:")
        print(f"  - invoice_origin: {invoice.invoice_origin}")
        print(f"  - invoice_line_ids count: {len(invoice.invoice_line_ids)}")

        # Method 1: From invoice lines with sale_line_ids (Most reliable)
        for line in invoice.invoice_line_ids:
            print(f"    Line: {line.name}, sale_line_ids: {bool(line.sale_line_ids)}")
            if line.sale_line_ids:
                so_id = line.sale_line_ids[0].order_id.id
                print(f"    Found SO from sale_line_ids: {line.sale_line_ids[0].order_id.name}")
                break

        # Method 2: From invoice_origin field - improved search
        if not so_id and invoice.invoice_origin:
            print(f"  Searching SO by origin: '{invoice.invoice_origin}'")
            # Try exact match first
            so = self.env['sale.order'].search([
                ('name', '=', invoice.invoice_origin)
            ], limit=1)

            if not so:
                # Try partial match in case of multiple references
                origin_parts = invoice.invoice_origin.split(',')
                for part in origin_parts:
                    part = part.strip()
                    if part:
                        so = self.env['sale.order'].search([
                            ('name', '=', part)
                        ], limit=1)
                        if so:
                            break

            if so:
                so_id = so.id
                print(f"    Found SO from origin: {so.name}")

        # Method 3: From team_id and origin (for specific Odoo configurations)
        if not so_id and invoice.invoice_origin:
            so = self.env['sale.order'].search([
                ('name', 'ilike', invoice.invoice_origin.split(',')[0].strip())
            ], limit=1)
            if so:
                so_id = so.id
                print(f"    Found SO from ilike search: {so.name}")

        # Method 4: From invoice lines with product and partner matching
        if not so_id:
            print("  Trying product/partner matching...")
            for line in invoice.invoice_line_ids:
                if line.product_id:
                    # Search for SO with same partner and product
                    so_lines = self.env['sale.order.line'].search([
                        ('product_id', '=', line.product_id.id),
                        ('order_id.partner_id', '=', invoice.partner_id.id),
                        ('order_id.state', 'in', ['sale', 'done']),
                        # Add date range for better matching
                        ('order_id.date_order', '<=', invoice.invoice_date or invoice.create_date),
                    ], order='id desc', limit=10)

                    # Check if any of these SO lines match the invoice line quantity/price
                    for so_line in so_lines:
                        if (abs(so_line.price_unit - line.price_unit) < 0.01 or
                                abs(so_line.product_uom_qty - line.quantity) < 0.01):
                            so_id = so_line.order_id.id
                            print(f"    Found SO from product matching: {so_line.order_id.name}")
                            break
                    if so_id:
                        break

        # Method 5: From direct field if exists
        if not so_id:
            # Check common field names for SO reference
            so_fields = ['sale_order_id', 'x_sale_order_id', 'origin_sale_order_id']
            for field_name in so_fields:
                if hasattr(invoice, field_name):
                    field_value = getattr(invoice, field_name, None)
                    if field_value:
                        so_id = field_value.id if hasattr(field_value, 'id') else field_value
                        print(f"    Found SO from field {field_name}: {so_id}")
                        break

        print(f"  Final SO ID: {so_id}")
        return so_id

    def _prepare_move_lines_by_so(self, write_off_line_vals=None, force_balance=None, combined_distribution=None):
        '''Prepare move lines separated by Sales Order'''
        write_off_line_vals_list = write_off_line_vals or []
        so_groups = self._get_so_groups()
        total_invoice_amount = sum(group['total_amount'] for group in so_groups.values())

        line_vals_list = []

        for so_key, so_data in so_groups.items():
            # Calculate proportional amount for this SO
            proportion = so_data['total_amount'] / total_invoice_amount if total_invoice_amount else 0
            so_amount = self.amount * proportion

            # Prepare move lines for this SO
            so_lines = self._prepare_so_move_lines(so_key, so_data, so_amount, combined_distribution)
            print('so_lines => ', so_lines)
            line_vals_list.extend(so_lines)

        # Add write-off lines
        line_vals_list.extend(write_off_line_vals_list)

        return line_vals_list

    def _prepare_so_move_lines(self, so_key, so_data, so_amount, combined_distribution=None):
        '''Prepare move lines for specific Sales Order'''
        # Calculate amounts
        if self.payment_type == 'inbound':
            liquidity_amount_currency = so_amount
        elif self.payment_type == 'outbound':
            liquidity_amount_currency = -so_amount
        else:
            liquidity_amount_currency = 0.0

        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )

        counterpart_amount_currency = -liquidity_amount_currency
        counterpart_balance = -liquidity_balance
        currency_id = self.currency_id.id

        # Generate names with SO reference
        so_reference = ""
        if so_key != 'no_so' and so_data['so_record']:
            so_reference = f" - {so_data['so_record'].name}"

        liquidity_line_name = ''.join(x[1] for x in self._get_liquidity_aml_display_name_list()) + so_reference
        counterpart_line_name = ''.join(x[1] for x in self._get_counterpart_aml_display_name_list()) + so_reference

        liquidity_payload = {
            'name': liquidity_line_name,
            'date_maturity': self.date,
            'amount_currency': liquidity_amount_currency,
            'currency_id': currency_id,
            'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
            'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
            'partner_id': self.partner_id.id,
            'account_id': self.outstanding_account_id.id,
            'sale_order_reference': so_data['so_record'].name if so_data['so_record'] else False,
        }

        received_payload = {
            'name': counterpart_line_name,
            'date_maturity': self.date,
            'amount_currency': counterpart_amount_currency,
            'currency_id': currency_id,
            'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
            'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
            'partner_id': self.partner_id.id,
            'account_id': self.destination_account_id.id,
            'sale_order_reference': so_data['so_record'].name if so_data['so_record'] else False,
        }

        # Apply analytic distribution from SO if available, otherwise use combined distribution
        analytic_distribution = None

        if so_data['so_record']:
            if so_data['so_record'].do_ids and len(so_data['so_record'].do_ids) > 0:
                first_item_do = so_data['so_record'].do_ids[0]
                do_vehicle = first_item_do.vehicle_id
                analytic_account = self.env['account.move']._get_or_create_analytic_account((
                    do_vehicle.vehicle_name if do_vehicle else first_item_do.delivery_category_id.name,
                    '',
                    '',
                    do_vehicle.no_lambung if do_vehicle else first_item_do.product_category_id.name,
                    do_vehicle.product_category_id.name if do_vehicle else first_item_do.product_category_id.name,
                    do_vehicle.category_id.name if do_vehicle else first_item_do.delivery_category_id.name
                ))
                if analytic_account:
                    analytic_distribution = {str(analytic_account.id): 100}

        # If no SO-specific analytic distribution, use combined distribution
        if not analytic_distribution and combined_distribution:
            analytic_distribution = combined_distribution

        # Apply analytic distribution to both lines
        if analytic_distribution:
            liquidity_payload['analytic_distribution'] = analytic_distribution
            received_payload['analytic_distribution'] = analytic_distribution

        return [
            # Liquidity line
            liquidity_payload,
            # Receivable / Payable line
            received_payload,
        ]

    def _get_liquidity_aml_display_name_list(self):
        '''Override if needed for custom display names'''
        return super()._get_liquidity_aml_display_name_list()

    def _get_counterpart_aml_display_name_list(self):
        '''Override if needed for custom display names'''
        return super()._get_counterpart_aml_display_name_list()

# class AccountPaymentRegister(models.TransientModel):
#     _inherit = 'account.payment.register'
#
#     @api.model
#     def default_get(self, fields_list):
#         # OVERRIDE
#         res = super(APR, self).default_get(fields_list)
#
#         if 'line_ids' in fields_list and 'line_ids' not in res:
#
#             # Retrieve moves to pay from the context.
#
#             if self._context.get('active_model') == 'account.move':
#                 lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
#             elif self._context.get('active_model') == 'account.move.line':
#                 lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
#             else:
#                 raise UserError(_(
#                     "The register payment wizard should only be called on account.move or account.move.line records."
#                 ))
#
#             if 'journal_id' in res and not self.env['account.journal'].browse(res['journal_id']).filtered_domain([
#                 *self.env['account.journal']._check_company_domain(lines.company_id),
#                 ('type', 'in', ('bank', 'cash')),
#             ]):
#                 # default can be inherited from the list view, should be computed instead
#                 del res['journal_id']
#
#             # Keep lines having a residual amount to pay.
#             available_lines = self.env['account.move.line']
#             valid_account_types = self.env['account.payment']._get_valid_payment_account_types()
#             for line in lines:
#                 if line.move_id.state not in ['posted','sent']:
#                     raise UserError(_("You can only register payment for posted journal entries."))
#
#                 if line.account_type not in valid_account_types:
#                     continue
#                 if line.currency_id:
#                     if line.currency_id.is_zero(line.amount_residual_currency):
#                         continue
#                 else:
#                     if line.company_currency_id.is_zero(line.amount_residual):
#                         continue
#                 available_lines |= line
#
#             # Check.
#             if not available_lines:
#                 raise UserError(_("You can't register a payment because there is nothing left to pay on the selected journal items."))
#             if len(lines.company_id.root_id) > 1:
#                 raise UserError(_("You can't create payments for entries belonging to different companies."))
#             if len(set(available_lines.mapped('account_type'))) > 1:
#                 raise UserError(_("You can't register payments for both inbound and outbound moves at the same time."))
#
#             res['line_ids'] = [(6, 0, available_lines.ids)]
#
#         return res