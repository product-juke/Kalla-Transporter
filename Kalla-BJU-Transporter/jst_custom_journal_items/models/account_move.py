from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _name = 'account.move.line'
    _inherit = ['account.move.line', 'portfolio.view.mixin']

    is_hpp_line_from_bill = fields.Boolean(default=False)


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'portfolio.view.mixin']

    # Constants
    COGS_DISPLAY_TYPE = 'cogs'
    OUT_INVOICE_TYPE = 'out_invoice'
    OUT_REFUND_TYPE = 'out_refund'
    DRAFT_STATE = 'draft'
    FROZEN_PORTFOLIO = 'Frozen'
    VENDOR_ASSET_TYPE = 'vendor'

    @api.model
    def create(self, vals):
        """Override create to add COGS journal items on save if enabled"""
        _logger.info(f"COGS DEBUG => Creating move with vals: {vals}")

        move = super().create(vals)
        self._process_cogs_on_create(move)
        return move

    def write(self, vals):
        """Override write to add COGS journal items on save if enabled"""
        _logger.info(f"COGS DEBUG => Writing move with vals: {vals}")

        result = super().write(vals)
        self._process_cogs_on_write(vals)
        return result

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Override _reverse_moves to handle COGS creation for reversed invoices"""
        _logger.info("COGS DEBUG => Processing reverse moves")

        # Call the parent method to create reversed moves
        reversed_moves = super()._reverse_moves(default_values_list, cancel)

        # Process COGS for each reversed move that is an out_invoice
        for reversed_move in reversed_moves:
            if reversed_move.move_type == self.OUT_INVOICE_TYPE:
                _logger.info("COGS DEBUG => Processing COGS for reversed invoice ID: %s", reversed_move.id)
                try:
                    if self._should_create_cogs_items(reversed_move, 'on_reverse'):
                        _logger.info("COGS DEBUG => Creating COGS for reversed invoice ID: %s", reversed_move.id)
                        reversed_move._create_cogs_journal_items()
                    else:
                        _logger.info("COGS DEBUG => COGS conditions not met for reversed invoice ID: %s",
                                     reversed_move.id)
                except Exception as e:
                    _logger.error("COGS ERROR => Error in COGS processing for reversed invoice %s: %s",
                                  reversed_move.id, str(e))

        return reversed_moves

    def action_reverse(self):
        """Override action_reverse to ensure COGS processing on credit note reversal"""
        _logger.info("COGS DEBUG => Processing action_reverse")

        # Call the parent method
        result = super().action_reverse()

        # If the result contains a new invoice, process COGS for it
        if isinstance(result, dict) and result.get('res_id'):
            new_move_id = result['res_id']
            new_move = self.env['account.move'].browse(new_move_id)

            if new_move.move_type == self.OUT_INVOICE_TYPE:
                _logger.info("COGS DEBUG => Processing COGS for new invoice from reverse action ID: %s", new_move.id)
                try:
                    if self._should_create_cogs_items(new_move, 'on_reverse'):
                        _logger.info("COGS DEBUG => Creating COGS for new invoice from reverse ID: %s", new_move.id)
                        new_move._create_cogs_journal_items()
                    else:
                        _logger.info("COGS DEBUG => COGS conditions not met for new invoice from reverse ID: %s",
                                     new_move.id)
                except Exception as e:
                    _logger.error("COGS ERROR => Error in COGS processing for new invoice from reverse %s: %s",
                                  new_move.id, str(e))

        return result

    def _process_cogs_on_create(self, move):
        """Process COGS creation for newly created moves"""
        if move.move_type != self.OUT_INVOICE_TYPE:
            _logger.info("COGS DEBUG => Skipping COGS for move_type: %s", move.move_type)
            return

        try:
            if self._should_create_cogs_items(move):
                _logger.info("COGS DEBUG => Creating COGS for new move ID: %s", move.id)
                move._create_cogs_journal_items()
            else:
                _logger.info("COGS DEBUG => COGS conditions not met for move ID: %s", move.id)
        except Exception as e:
            _logger.error("COGS ERROR => Error in COGS processing for new move %s: %s", move.id, str(e))

    def _process_cogs_on_write(self, vals):
        """Process COGS creation for updated moves"""
        relevant_fields = ['line_ids', 'partner_id', 'move_type', 'state']

        if not any(field in vals for field in relevant_fields):
            return

        _logger.info("COGS DEBUG => Relevant fields changed: %s",
                     [field for field in relevant_fields if field in vals])

        for move in self:
            if move.move_type != self.OUT_INVOICE_TYPE:
                _logger.info("COGS DEBUG => Skipping COGS for move %s with move_type: %s",
                             move.id, move.move_type)
                continue

            try:
                if self._should_create_cogs_items(move, 'on_write'):
                    _logger.info("COGS DEBUG => Creating COGS for updated move ID: %s", move.id)
                    move._create_cogs_journal_items()
            except Exception as e:
                _logger.error("COGS ERROR => Error in COGS processing for move %s: %s",
                              move.id, str(e))

    def _should_create_cogs_items(self, move=None, event='on_create'):
        """Check if COGS journal items should be created"""
        if not move:
            move = self

        conditions = {
            'cogs_enabled': self._is_cogs_enabled(),
            'is_out_invoice': move.move_type == self.OUT_INVOICE_TYPE,
            'has_highest_bop': move._has_highest_bop(),
            'not_frozen': move.env.company.portfolio_id.name != self.FROZEN_PORTFOLIO
        }
        if event == 'on_create':
            conditions['is_draft'] = move.state == self.DRAFT_STATE
        # For reversed invoices, we allow any state since they might be created in posted state

        _logger.info("COGS DEBUG => COGS conditions for move %s (event: %s): %s", move.id, event, conditions)

        return all(conditions.values())

    def _is_cogs_enabled(self):
        """Check if COGS is enabled in system parameters"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'account.enable_cogs_journal_items', default=False
        )

    def _has_highest_bop(self):
        """Check if current invoice has the highest BOP among related DO"""
        _logger.info("COGS DEBUG => Checking highest BOP for move ID: %s", self.id)

        try:
            if not self.invoice_origin:
                _logger.info("COGS DEBUG => No invoice_origin found")
                return False

            sale_orders = self._get_related_sale_orders()
            if not sale_orders:
                return False

            do_id = self._get_do_ids_with_asset_vehicle(sale_orders)
            if do_id == 'vli_do':
                return True

            if not do_id:
                return False

            bop_data = self._get_bop_data_for_do(do_id)
            vendor_bill_exists = self._has_vendor_bill()

            if not vendor_bill_exists and not bop_data and not do_id:
                if not vendor_bill_exists:
                    _logger.info("COGS DEBUG => No vendor bill found for move %s", self.id)
                if not bop_data:
                    _logger.info("COGS DEBUG => No BOP DATA found for move %s", self.id)

                return False

            _logger.info(f"COGS DEBUG => {bop_data}")

            highest_bop_value = len(bop_data) > 0
            return highest_bop_value or vendor_bill_exists or do_id
            # highest_bop_value = [bop[0][2] for bop in bop_data]  # BOP value from query result
            # return sum(highest_bop_value) > 0 or vendor_bill_exists

        except Exception as e:
            _logger.error("COGS ERROR => Error in _has_highest_bop: %s", str(e))
            return False

    def _get_related_sale_orders(self):
        """Get sale orders related to this invoice"""
        invoice_origins = str(self.invoice_origin).split(', ')
        orders = self.env['sale.order'].search([('name', 'in', invoice_origins)])

        if orders:
            _logger.info("COGS DEBUG => Found SO: %s (IDs: %s)",
                         orders.mapped('name'), orders.mapped('id'))
        else:
            _logger.info("COGS DEBUG => No sale orders found for origins: %s", invoice_origins)

        return orders

    def _get_do_ids_with_asset_vehicle(self, sale_orders):
        """Get DO ID that has asset vehicle (not vendor type)"""
        all_do_ids = []

        for so in sale_orders:
            if str(so.product_category_id.name).upper() == 'VLI':
                return 'vli_do'

            for line in so.order_line:
                if (line.do_id and
                        str(line.do_id.vehicle_id.asset_type).lower() != self.VENDOR_ASSET_TYPE and
                        str(line.do_id.product_category_id.name).upper() != 'VLI'):
                    _logger.info("COGS DEBUG => Found DO ID: %s", line.do_id.id)
                    all_do_ids.append(line.do_id.id)
                elif line.do_id and str(line.do_id.vehicle_id.asset_type).lower() == self.VENDOR_ASSET_TYPE:
                    _logger.info("COGS DEBUG => Elif: Found DO ID: %s", line.do_id.id)
                    all_do_ids.append(line.do_id.id)

        if all_do_ids:
            return list(set(all_do_ids))  # pakai set untuk hilangkan duplikat
        else:
            _logger.info("COGS DEBUG => No DO with asset vehicle found")
            return None

    def _has_vendor_bill(self):
        """Check if vendor bill exists for this move"""
        query = """
            SELECT DISTINCT fd.purchase_order_id
            FROM account_move_line aml
                INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                INNER JOIN fleet_do fd ON fd.id = sol.do_id
                INNER JOIN account_move_purchase_order_rel ampor ON ampor.purchase_order_id = fd.purchase_order_id
                INNER JOIN account_move am ON am.id = ampor.account_move_id
            WHERE aml.move_id = %s
            LIMIT 1
        """

        self.env.cr.execute(query, (self.id,))
        result = self.env.cr.fetchone()

        _logger.info("COGS DEBUG => Vendor bill check result: %s", bool(result))
        return bool(result)

    def _get_bop_data_for_do(self, do_id):
        """Get BOP data for specific DO"""
        # Handle both single DO ID and list of DO IDs
        if isinstance(do_id, list):
            if len(do_id) == 1:
                # Single item in list, use simple equality
                query = """
                    SELECT 
                        sol.order_id,
                        so.name as sale_order_name,
                        MAX(sol.bop) as max_bop,
                        dplr.do_id
                    FROM do_po_line_rel dplr
                    JOIN sale_order_line sol ON sol.id = dplr.po_line_id
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE dplr.do_id = %s AND sol.bop IS NOT NULL
                    GROUP BY sol.order_id, so.name, dplr.do_id
                    ORDER BY max_bop DESC, sol.order_id ASC
                """
                self.env.cr.execute(query, (do_id[0],))
            else:
                # Multiple items, use IN operator
                query = """
                    SELECT 
                        sol.order_id,
                        so.name as sale_order_name,
                        MAX(sol.bop) as max_bop,
                        dplr.do_id
                    FROM do_po_line_rel dplr
                    JOIN sale_order_line sol ON sol.id = dplr.po_line_id
                    JOIN sale_order so ON so.id = sol.order_id
                    WHERE dplr.do_id IN %s AND sol.bop IS NOT NULL
                    GROUP BY sol.order_id, so.name, dplr.do_id
                    ORDER BY max_bop DESC, sol.order_id ASC
                """
                self.env.cr.execute(query, (tuple(do_id),))
        else:
            # Single DO ID (not in list)
            query = """
                SELECT 
                    sol.order_id,
                    so.name as sale_order_name,
                    MAX(sol.bop) as max_bop,
                    dplr.do_id
                FROM do_po_line_rel dplr
                JOIN sale_order_line sol ON sol.id = dplr.po_line_id
                JOIN sale_order so ON so.id = sol.order_id
                WHERE dplr.do_id IN %s AND sol.bop IS NOT NULL
                GROUP BY sol.order_id, so.name, dplr.do_id
                ORDER BY max_bop DESC, sol.order_id ASC
            """
            self.env.cr.execute(query, (tuple(do_id),))

        results = self.env.cr.fetchall()
        _logger.info("COGS DEBUG => BOP data query results: %s", results)

        all_invoices_status = []

        for result in results:
            so_id = result[0] if result[0] is not None else None
            order = self.env['sale.order'].search([
                ('id', '=', so_id)
            ], limit=1)
            _logger.info(f"COGS DEBUG => ORDER ID: {so_id}")

            invoices = order.invoice_ids.filtered(lambda x: x.id != self.id)
            all_invoice_is_cancel = invoices and all(inv.state == 'cancel' for inv in invoices)
            _logger.info(f"COGS DEBUG => Invoices: {invoices} => All is cancel: {all_invoice_is_cancel}")

            all_invoices_status.append(all_invoice_is_cancel)

            if not all_invoice_is_cancel and any(line.is_invoiced for line in order.order_line):
                return []

        if not all(status == True for status in all_invoices_status):
            return []

        return results

    def _get_bop_and_bill_amounts_with_analytics(self):
        """Get BOP and bill amounts with their analytic distributions"""
        _logger.info("COGS DEBUG => Getting BOP and bill amounts with analytics")

        if not self.invoice_origin:
            _logger.warning("COGS WARNING => No invoice_origin found")
            return self._empty_amounts_result()

        try:
            sale_orders = self._get_related_sale_orders()
            if not sale_orders:
                return self._empty_amounts_result()

            do_ids = self._get_do_ids_with_asset_vehicle(sale_orders)
            if not do_ids and do_ids != 'vli_do':
                return self._empty_amounts_result()

            # Get amounts and analytics
            bop_data = []
            if do_ids == 'vli_do':
                do_ids = []
                order_lines = self.line_ids.sale_line_ids
                _logger.info(f"COGS DEBUG VLI => Sale Line ({len(order_lines)}) -> {order_lines}")
                for line in order_lines:
                    if line.do_id.id not in do_ids:
                        do_ids.append(line.do_id.id)

                _logger.info(f"COGS DEBUG VLI => DO IDs ({len(do_ids)}) -> {do_ids}")
                bop_data = self._get_bop_amount_and_analytics(do_ids, is_vli=True)

            elif do_ids != 'vli_do':
                bop_data = self._get_bop_amount_and_analytics(do_ids, is_vli=False)
            bill_data = self._get_bill_amount_and_analytics(do_ids)
            bill_vli_shipment_datas = self._get_bill_amount_and_analytics_for_vli('Car Carrier')
            bill_self_drive_datas = self._get_bill_amount_and_analytics_for_self_drive()

            _logger.info(("COGS DEBUG => Final amounts - BOP: %s, Bill: %s, DO ID: %s, BILL VLI DATA: %s, BILL SELF DRIVE DATA: %s, EACH ANALYTIC DISTRIBUTION: %s",
                         bop_data[0] if bop_data else None, bill_data[0] if bill_data else None, do_ids, bill_vli_shipment_datas, bill_self_drive_datas, bop_data[2] if bop_data else None))

            return (bop_data[0] if bop_data else None, bill_data[0] if bill_data else None, do_ids,
                    bop_data[1] if bop_data else None, bill_data[1] if bill_data else None, bill_vli_shipment_datas, bill_self_drive_datas, bop_data[2] if bop_data else None, bop_data[3] if bop_data and len(bop_data) > 3 else None)

        except Exception as e:
            _logger.error(("COGS ERROR => Error in _get_bop_and_bill_amounts_with_analytics: %s", str(e)))
            return self._empty_amounts_result()

    def _empty_amounts_result(self):
        """Return empty result tuple"""
        return 0.0, 0.0, None, None, None, None, None, None, None

    def _get_bop_biaya_tambahan(self, do_ids):
        formatted_additional_values = []
        additional_bop_values = self.env['bop.line'].search([
            ('fleet_do_id', 'in', tuple(do_ids) if isinstance(do_ids, list) else do_ids),
            ('is_additional_cost', '=', True),
            '|',
            ('invoice_id', '=', False),
            ('invoice_id.state', '=', 'cancel')  # atau invoice dengan state cancel
        ])

        _logger.info(f"COGS DEBUG => Additional BOP Values: {additional_bop_values}")

        for val in additional_bop_values:
            bop_dict = {
                'bop': val.amount_paid,
                'label': ", ".join(val.product_ids.mapped('name')),
                'analytic_distribution': self._create_analytic_distribution(val),
            }
            formatted_additional_values.append(bop_dict)
            val.sudo().write({'invoice_id': self.id})

        return formatted_additional_values

    def _get_bop_amount_and_analytics(self, do_ids, is_vli):
        """Get BOP amount and create analytic distribution"""
        try:
            # Handle both single DO ID and list of DO IDs
            if isinstance(do_ids, list):
                if len(do_ids) == 1:
                    query = """
                        SELECT sol.bop AS highest_bop, sol.id as sol_id
                        FROM sale_order_line sol
                        WHERE sol.do_id = %s AND sol.is_header = TRUE
                    """
                    self.env.cr.execute(query, (do_ids[0],))
                    _logger.info(f'COGS DEBUG => Masuk kondisi 1. {(query, (do_ids[0],))}')
                else:
                    query = """
                        SELECT sol.bop AS highest_bop, sol.id as sol_id
                        FROM sale_order_line sol
                        WHERE sol.do_id IN %s AND sol.is_header = TRUE
                    """
                    self.env.cr.execute(query, (tuple(do_ids),))
                    _logger.info(f'COGS DEBUG => Masuk kondisi 2. {(query, (tuple(do_ids),))}')
            else:
                query = """
                    SELECT sol.bop AS highest_bop, sol.id as sol_id
                    FROM sale_order_line sol
                    WHERE sol.do_id = %s AND sol.is_header = TRUE
                """
                self.env.cr.execute(query, (do_ids,))
                _logger.info(f'COGS DEBUG => Masuk kondisi 3. {(query, (do_ids,))}')

            results = self.env.cr.fetchall()

            sol_ids = []
            bop_values = []
            is_no_results = not results or len(results) < 1

            if is_vli:
                purchases = self.env['purchase.order'].search([
                    ('fleet_do_id', 'in', do_ids)
                ])

                if len(purchases) < 1:
                    return [], None, None

                for purchase in purchases:
                    if str(purchase.fleet_do_id.asset_type).lower() != 'vendor':
                        bop_values.append(sum(purchase.order_line.mapped('price_subtotal')))
                        _logger.info(f'COGS DEBUG VLI => BOP Values: {bop_values}')
                        for line in purchase.fleet_do_id.po_line_ids:
                            sol_ids.append(line.id)

                _logger.info(f'COGS DEBUG VLI => SOL IDs: {sol_ids}')

            _logger.info(f"COGS DEBUG => Results Query BOP Amounts: {results} - {bop_values}")

            if is_no_results and not is_vli:
                return [], None, None

            if not is_vli:
                for result in results:
                    sol_id = result[1] if result[1] is not None else None
                    bop_value = result[0] if result[0] is not None else None
                    _logger.info(f"COGS DEBUG => SOL ID: {sol_id}")
                    _logger.info(f"COGS DEBUG => BOP Value: {bop_value}")

                    so_line = self.env['sale.order.line'].search([
                        ('id', '=', sol_id),
                    ], limit=1)

                    invoices = so_line.order_id.invoice_ids.filtered(lambda x: x.id != self.id)
                    all_invoice_is_cancel = invoices and all(inv.state == 'cancel' for inv in invoices)
                    _logger.info(f"COGS DEBUG => Invoices: {invoices} => All is cancel: {all_invoice_is_cancel}")

                    if (not so_line.is_invoiced or all_invoice_is_cancel) and (str(so_line.do_id.asset_type_name).lower() != 'vendor'):
                        bop_values.append(bop_value)
                        so_line.is_invoiced = True

            # BOP Additional
            formatted_additional_values = self._get_bop_biaya_tambahan(do_ids)

            # Create analytic distribution
            if not is_vli:
                sol_ids = [result[1] for result in results]

            sol_records = self.env['sale.order.line'].browse(sol_ids)
            if len(sol_records) > 1:
                analytic_distribution = {}
                each_analytic_distribution = {}
                for index, sol in enumerate(sol_records, start=1):
                    analytic_distribution.update(self._create_analytic_distribution(sol))
                    each_analytic_distribution[index] = self._create_analytic_distribution(sol)
            else:
                analytic_distribution = self._create_analytic_distribution(sol_records[0])
                each_analytic_distribution = self._create_analytic_distribution(sol_records[0])

            _logger.info(("COGS DEBUG => BOP amount: %s, Analytics: %s, Each Analytic Distribution: %s", bop_values, analytic_distribution, each_analytic_distribution))
            return bop_values if not is_vli else [], analytic_distribution, each_analytic_distribution, formatted_additional_values

        except Exception as e:
            _logger.error(("COGS ERROR => Error getting BOP amount: %s", str(e)))
            return 0.0, None, None, None

    def _get_bill_amount_and_analytics(self, do_ids):
        """Get bill amount and create analytic distribution"""
        _logger.info('COGS DEBUG => _get_bill_amount_and_analytics() is starting..')
        try:
            query = """
                SELECT DISTINCT
                    fd.vehicle_id,
                    am.amount_untaxed
                FROM account_move_line aml
                    INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                    INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                    INNER JOIN fleet_do fd ON fd.id = sol.do_id
                    INNER JOIN account_move_purchase_order_rel ampor ON ampor.purchase_order_id = fd.purchase_order_id
                    INNER JOIN account_move am ON am.id = ampor.account_move_id
                    inner join fleet_vehicle_model_category fvmc on fvmc.id = fd.category_id 
                    inner join program_category pc on pc.id = fvmc.program_category_id 
                WHERE aml.move_id = %s AND sol.is_header = TRUE AND UPPER(pc."name") != 'SHIPMENT'AND UPPER(pc."name") != 'CAR CARRIER'
                LIMIT 1
            """

            self.env.cr.execute(query, (self.id,))
            result = self.env.cr.dictfetchone()
            _logger.info(f'COGS DEBUG => Query Result {result}')

            if not result and do_ids:
                purchases = self.env['purchase.order'].search([
                    ('fleet_do_id', 'in', do_ids)
                ])

                _logger.info(f"DO IDs: {do_ids}")
                _logger.info(f"Purchases: {purchases}")

                if len(purchases) < 1:
                    return 0.0, None

                for purchase in purchases:
                    if str(purchase.fleet_do_id.asset_type).lower() == 'vendor':
                        result = {
                            'amount_untaxed': sum(purchase.order_line.mapped('price_subtotal')),
                            'vehicle_id': purchase.fleet_do_id.vehicle_id.id
                        }

                _logger.info(f'COGS DEBUG VENDOR => Result: {result}')

            if not result or not result.get('amount_untaxed'):
                return 0.0, None

            bill_value = float(result['amount_untaxed'])
            if bill_value <= 0:
                return 0.0, None

            # Create analytic distribution
            vehicle_id = result.get('vehicle_id')
            analytic_distribution = self._create_vehicle_analytic_distribution(vehicle_id)

            _logger.info("COGS DEBUG => Bill amount: %s, Analytics: %s", bill_value, analytic_distribution)
            return bill_value, analytic_distribution

        except Exception as e:
            _logger.error("COGS ERROR => Error getting bill amount: %s", str(e))
            return 0.0, None

    def _get_bill_amount_and_analytics_for_vli(self, program_name):
        """Get bill amount and create analytic distribution"""
        try:
            if program_name == 'Car Carrier':
                query_exist_shipment_line = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM account_move_line aml
                        INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                        INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                        INNER JOIN fleet_do fd ON fd.id = sol.do_id
                        INNER JOIN account_move am ON am.id = aml.move_id
                        INNER JOIN product_product pp ON pp.id = sol.product_id
                        INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = pp.vehicle_category_id
                        LEFT JOIN program_category pc ON pc.id = fvmc.program_category_id
                        WHERE aml.move_id = %s
                        AND UPPER(pc."name") = 'CAR CARRIER'
                    ) AS has_shipment_category;
                """
            else:
                query_exist_shipment_line = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM account_move_line aml
                        INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                        INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                        INNER JOIN fleet_do fd ON fd.id = sol.do_id
                        INNER JOIN account_move_purchase_order_rel ampor ON ampor.purchase_order_id = fd.purchase_order_id
                        INNER JOIN account_move am ON am.id = ampor.account_move_id
                        INNER JOIN product_product pp ON pp.id = sol.product_id
                        INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = pp.vehicle_category_id
                        LEFT JOIN program_category pc ON pc.id = fvmc.program_category_id
                        WHERE aml.move_id = %s
                        AND am.move_type = 'in_invoice'
                        AND UPPER(pc."name") in ('SHIPMENT', 'CAR CARRIER')
                    ) AS has_shipment_category;
                """
            self.env.cr.execute(query_exist_shipment_line, (self.id, ))
            row_exist = self.env.cr.dictfetchone()
            _logger.info(f"COGS DEBUG => {row_exist}, {row_exist.get('has_shipment_category')}")
            if row_exist.get('has_shipment_category') is not True:
                return []

            if program_name == 'Car Carrier':
                query = """
                    SELECT DISTINCT
                        fd.vehicle_id,
                        sol.bop as bop,
                        fvmc."name" as category_name
                    FROM account_move_line aml
                        INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                        INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                        INNER JOIN fleet_do fd ON fd.id = sol.do_id
                        INNER JOIN account_move am ON am.id = aml.move_id
                        inner join product_product pp on pp.id = sol.product_id 
                        inner join fleet_vehicle_model_category fvmc on fvmc.id = pp.vehicle_category_id 
                        left join program_category pc on pc.id = fvmc.program_category_id 
                    WHERE aml.move_id = %s
                        AND sol.bop > 0
                """
            else:
                query = """
                    SELECT DISTINCT
                        fd.vehicle_id,
                        sol.bop as bop,
                        fvmc."name" as category_name
                    FROM account_move_line aml
                        INNER JOIN sale_order_line_invoice_rel solir ON solir.invoice_line_id = aml.id
                        INNER JOIN sale_order_line sol ON sol.id = solir.order_line_id
                        INNER JOIN fleet_do fd ON fd.id = sol.do_id
                        INNER JOIN account_move_purchase_order_rel ampor ON ampor.purchase_order_id = fd.purchase_order_id
                        INNER JOIN account_move am ON am.id = ampor.account_move_id
                        inner join product_product pp on pp.id = sol.product_id 
                        inner join fleet_vehicle_model_category fvmc on fvmc.id = pp.vehicle_category_id 
                        left join program_category pc on pc.id = fvmc.program_category_id 
                    WHERE aml.move_id = %s
                        AND sol.bop > 0
                        AND am.move_type = 'in_invoice'
                """

            self.env.cr.execute(query, (self.id,))
            results = self.env.cr.dictfetchall()

            if not results:
                return []

            # Create analytic distribution
            for index, result in enumerate(results):
                vehicle_id = result.get('vehicle_id')
                analytic_distribution = self._create_vehicle_analytic_distribution(vehicle_id)
                results[index]['analytic_distribution'] = analytic_distribution

                _logger.info("COGS DEBUG => Result Bill VLI: %s", results[index])

            _logger.info("COGS DEBUG => All Results Bill VLI: %s", results)
            return results

        except Exception as e:
            _logger.error("COGS ERROR => Error getting bill amount: %s", str(e))
            return []

    def _get_bill_amount_and_analytics_for_self_drive(self):
        """Get bill amount and create analytic distribution"""
        try:
            query_exist_self_drive_line = """
            SELECT EXISTS (
                select
                    1
                from
                    sale_order_line_invoice_rel solir
                inner join account_move_line aml on
                    aml.id = solir.invoice_line_id
                inner join account_move am on
                    am.id = aml.move_id
                inner join sale_order_line sol on
                    sol.id = solir.order_line_id
                inner join sale_order so on
                    so.id = sol.order_id
                inner join product_product pp on
                    pp.id = aml.product_id
                inner join fleet_vehicle_model_category fvmc on
                    fvmc.id = pp.vehicle_category_id
                left join program_category pc on
                    pc.id = fvmc.program_category_id
                where
                    am.id = %s
                    and UPPER(pc."name") = 'SELF DRIVE'
            ) AS has_self_drive_category;
            """
            self.env.cr.execute(query_exist_self_drive_line, (self.id, ))
            row_exist = self.env.cr.dictfetchone()
            _logger.info(f"COGS DEBUG => {row_exist}, {row_exist.get('has_self_drive_category')}")
            if row_exist.get('has_self_drive_category') is not True:
                return []

            query = """
                select distinct 
                    am_bill.name,
                    pc1.name as product_category_name,
                    fvmc.name as category_name,
                    fd.driver_id,
                    am_bill.amount_untaxed
                from
                    sale_order_line_invoice_rel solir
                inner join account_move_line aml on
                    aml.id = solir.invoice_line_id
                inner join sale_order_line sol on
                    sol.id = solir.order_line_id
                inner join sale_order so on
                    so.id = sol.order_id
                inner join fleet_do fd on
                    fd.id = sol.do_id
                inner join product_product pp on
                    pp.id = aml.product_id
                inner join fleet_vehicle_model_category fvmc on
                    fvmc.id = pp.vehicle_category_id
                inner join product_category pc1 on
                    pc1.id = fvmc.product_category_id 
                inner join bop_line bl on
                    bl.fleet_do_id = fd.id
                inner join account_move as am_bill on
                    am_bill.id = bl.vendor_bill_id
                left join program_category pc on
                    pc.id = fvmc.program_category_id
                where
                    aml.move_id = %s
                    and (UPPER(pc."name") != 'SELF DRIVE'
                        or pc."name" is null)
            """

            self.env.cr.execute(query, (self.id,))
            results = self.env.cr.dictfetchall()

            if not results:
                return []

            # Create analytic distribution
            for index, result in enumerate(results):
                driver_id = result.get('driver_id')
                category_name = 'Self Drive'
                product_category_name = result.get('product_category_name')
                analytic_distribution = self._create_driver_analytic_distribution(driver_id, category_name, product_category_name)
                results[index]['analytic_distribution'] = analytic_distribution

                _logger.info("COGS DEBUG => Result Bill SELF DRIVE: %s", results[index])

            _logger.info("COGS DEBUG => All Results Bill SELF DRIVE: %s", results)
            return results

        except Exception as e:
            _logger.error("COGS ERROR => Error getting bill SELF DRIVE amount: %s", str(e))
            return []

    def _create_analytic_distribution(self, sol_record):
        """Create analytic distribution from sale order line"""
        if not sol_record.exists() or 'do_id' not in sol_record:
            if 'fleet_do_id' not in sol_record:
                return None

        do = None
        if 'do_id' in sol_record:
            do = sol_record.do_id
        elif 'fleet_do_id' in sol_record:
            do = sol_record.fleet_do_id

        if do:
            vehicle = do.vehicle_id
            return self._create_vehicle_analytic_distribution(vehicle.id)

        return None

    def _create_vehicle_analytic_distribution(self, vehicle_id):
        """Create analytic distribution from vehicle"""
        if not vehicle_id:
            return None

        vehicle = self.env['fleet.vehicle'].browse(vehicle_id)
        if not vehicle.exists():
            return None

        analytic_account = self._get_or_create_analytic_account((
            vehicle.vehicle_name,
            '',
            '',
            vehicle.no_lambung,
            vehicle.product_category_id.name,
            vehicle.category_id.name
        ))

        return {str(analytic_account.id): 100}

    def _create_driver_analytic_distribution(self, driver_id, category_name, product_category_name):
        """Create analytic distribution from vehicle"""
        if not driver_id:
            return None

        partner = self.env['res.partner'].browse(driver_id)
        if not partner.exists():
            return None

        analytic_account = self._get_or_create_analytic_account((
            partner.name,
            '',
            '',
            category_name,
            product_category_name,
            category_name
        ))

        return {str(analytic_account.id): 100}

    def _create_cogs_journal_items(self):
        """Create COGS journal items using configured accounts"""
        _logger.info("COGS DEBUG => Creating COGS journal items for move %s", self.id)

        try:
            accounts = self._get_cogs_accounts()
            if not accounts:
                return False

            income_account, expense_account = accounts

            # Check for existing COGS items
            if self._has_existing_cogs_items(income_account, expense_account):
                _logger.info("COGS DEBUG => COGS items already exist, skipping")
                return

            # Get amounts and analytics
            amounts_data = self._get_bop_and_bill_amounts_with_analytics()
            bop_amounts, bill_amount, do_ids, bop_analytics, bill_analytics, bill_vli_shipment_datas, bill_self_drive_datas, each_analytic_distribution, additional_bop_values = amounts_data

            if self._should_skip_cogs_creation(bop_amounts, bill_amount, do_ids, bill_vli_shipment_datas, bill_self_drive_datas):
                return

            # Create journal lines
            new_lines = self._create_cogs_lines(
                bop_amounts, bill_amount,
                bop_analytics, bill_analytics,
                bill_vli_shipment_datas, bill_self_drive_datas,
                income_account, expense_account,
                each_analytic_distribution, additional_bop_values
            )

            _logger.info(f"COGS DEBUG => new_lines => {new_lines}")
            new_line_names = [line_vals[2].get("name") for line_vals in new_lines]

            if self._has_existing_cogs_items(income_account, expense_account, new_line_names):
                _logger.info("COGS DEBUG => Some COGS items already exist, skipping duplicates")
                # Filter hanya line yang belum ada
                new_lines = [
                    line_vals for line_vals in new_lines
                    if not self._has_existing_cogs_items(
                        income_account, expense_account, [line_vals[2].get("name")]
                    )
                ]

            if new_lines:
                self._apply_cogs_lines(new_lines, bop_amounts, bill_amount)

        except Exception as e:
            _logger.error("COGS ERROR => Error in _create_cogs_journal_items: %s", str(e))
            return False

    def _get_cogs_accounts(self):
        """Get configured COGS accounts"""
        income_account_id = self.env['ir.config_parameter'].sudo().get_param(
            'account.cogs_income_account_id'
        )
        expense_account_id = self.env['ir.config_parameter'].sudo().get_param(
            'account.cogs_expense_account_id'
        )

        if not income_account_id or not expense_account_id:
            _logger.info("COGS DEBUG => COGS accounts not configured")
            return None

        income_account = self.env['account.account'].browse(int(income_account_id))
        expense_account = self.env['account.account'].browse(int(expense_account_id))

        if not income_account.exists():
            raise UserError("Configured COGS Income Account tidak ditemukan! Silakan periksa pengaturan.")

        if not expense_account.exists():
            raise UserError("Configured COGS Expense Account tidak ditemukan! Silakan periksa pengaturan.")

        return income_account, expense_account

    def _has_existing_cogs_items(self, income_account, expense_account, new_line_names=None):
        """
        Check if COGS items already exist.
        Only skip if the exact same line (name + account) already exists.
        """
        if not new_line_names:
            new_line_names = []

        for line in self.line_ids:
            if (
                    line.display_type == self.COGS_DISPLAY_TYPE and
                    (line.account_id.id == income_account.id or line.account_id.id == expense_account.id) and
                    line.name in new_line_names
            ):
                _logger.info("COGS DEBUG => Found duplicate COGS line: %s", line.name)
                return True

        return False

    # def _has_existing_cogs_items(self, income_account, expense_account):
    #     """Check if COGS items already exist"""
    #     existing_income = False
    #     existing_expense = False
    #
    #     for index, line in enumerate(self.line_ids):
    #         if (
    #             line.account_id.id == income_account.id and
    #             line.display_type == self.COGS_DISPLAY_TYPE and
    #             f'Highest BOP ({index + 1})' in line.name
    #         ):
    #             existing_income = True
    #
    #     for index, line in enumerate(self.line_ids):
    #         if (
    #             line.account_id.id == expense_account.id and
    #             line.display_type == self.COGS_DISPLAY_TYPE and
    #             f'Highest BOP ({index + 1})' in line.name
    #         ):
    #             existing_expense = True
    #
    #     return bool(existing_income or existing_expense)

    def _should_skip_cogs_creation(self, bop_amount, bill_amount, do_ids, bill_vli_shipment_datas, bill_self_drive_datas):
        """Check if COGS creation should be skipped"""
        if not do_ids or (isinstance(do_ids, list) and len(do_ids) < 1):
            _logger.info("COGS DEBUG => No DO_ID exists, exiting")
            return True

        if len(bill_vli_shipment_datas) < 1 and len(bill_self_drive_datas) < 1 and (not bop_amount or (isinstance(bop_amount, list) and len(bop_amount) == 0)) and bill_amount <= 0:
            if len(bill_vli_shipment_datas) < 1:
                _logger.info("COGS DEBUG => No bill_vli_shipment_datas exists, exiting")
            elif len(bill_self_drive_datas) < 1:
                _logger.info("COGS DEBUG => No bill_self_drive_datas exists, exiting")
            else:
                _logger.info("COGS DEBUG => No amounts to process, exiting")
            return True

        return False

    def _create_cogs_lines(self, bop_amounts, bill_amount, bop_analytics, bill_analytics,
                           bill_vli_shipment_datas, bill_self_drive_datas, income_account, expense_account, each_analytic_distribution, additional_bop_values):
        """Create COGS journal lines"""
        new_lines = []

        if bop_amounts and len(bop_amounts) > 0:
            for index, bop_amount in enumerate(bop_amounts):
                new_lines.extend(self._create_bop_lines(
                    bop_amount, bop_analytics, income_account, expense_account, index
                ))

        if additional_bop_values and len(additional_bop_values) > 0:
            for index, value in enumerate(additional_bop_values):
                new_lines.extend(self._create_bop_additional_lines(
                    value, bop_analytics, income_account, expense_account, index
                ))

        if bill_amount and bill_amount > 0:
            new_lines.extend(self._create_bill_lines(
                bill_amount, bill_analytics, income_account, expense_account
            ))
        elif len(bill_vli_shipment_datas) > 0:
            for res in bill_vli_shipment_datas:
                new_lines.extend(self._create_vli_bill_lines(
                    res.get('bop'), res.get('analytic_distribution'), res.get('category_name'), income_account, expense_account
                ))
        elif len(bill_self_drive_datas) > 0:
            for res in bill_self_drive_datas:
                new_lines.extend(self._create_vli_bill_lines(
                    res.get('amount_untaxed'), res.get('analytic_distribution'), 'Self Drive', income_account, expense_account
                ))

        _logger.info("COGS DEBUG => Created %s new lines", len(new_lines))
        return new_lines

    def _create_bop_lines(self, amount, analytics, income_account, expense_account, index, label='COGS Highest BOP'):
        """Create BOP-related journal lines"""
        lines = []

        if amount > 0.0:
            # Credit line for Income Account (BOP)
            # for index, amount in enumerate(amounts):
            income_line = self._create_line_data(
                income_account, f"{label} ({index + 1}) - {income_account.name}",
                0.0, amount, analytics
            )
            lines.append((0, 0, income_line))

            # Debit line for Expense Account (BOP)
            # for index, amount in enumerate(amounts):
            expense_line = self._create_line_data(
                expense_account, f"{label} ({index + 1}) - {expense_account.name}",
                amount, 0.0, analytics
            )
            lines.append((0, 0, expense_line))

        return lines

    def _create_bop_additional_lines(self, value, analytics, income_account, expense_account, index, label='Biaya Tambahan'):
        """Create BOP-related journal lines"""
        lines = []

        # Credit line for Income Account (BOP)
        # for index, amount in enumerate(amounts):
        income_line = self._create_line_data(
            income_account, f"{label} - {value['label']} - {income_account.name}",
            0.0, value['bop'], value['analytic_distribution']
        )
        lines.append((0, 0, income_line))

        # Debit line for Expense Account (BOP)
        # for index, amount in enumerate(amounts):
        expense_line = self._create_line_data(
            expense_account, f"{label} - {value['label']} - {expense_account.name}",
            value['bop'], 0.0, value['analytic_distribution']
        )
        lines.append((0, 0, expense_line))

        return lines

    def _create_bill_lines(self, amount, analytics, income_account, expense_account):
        """Create Bill-related journal lines"""
        lines = []

        # Credit line for Income Account (Bill)
        income_line = self._create_line_data(
            income_account, f"COGS Vendor Bill - {income_account.name}",
            0.0, amount, analytics
        )
        lines.append((0, 0, income_line))

        # Debit line for Expense Account (Bill)
        expense_line = self._create_line_data(
            expense_account, f"COGS Vendor Bill - {expense_account.name}",
            amount, 0.0, analytics
        )
        lines.append((0, 0, expense_line))

        return lines

    def _create_vli_bill_lines(self, amount, analytics, category_name, income_account, expense_account):
        """Create Bill-related journal lines"""
        lines = []

        # Credit line for Income Account (Bill)
        income_line = self._create_line_data(
            income_account, f"COGS Vendor Bill - {category_name} - {income_account.name}",
            0.0, amount, analytics
        )
        lines.append((0, 0, income_line))

        # Debit line for Expense Account (Bill)
        expense_line = self._create_line_data(
            expense_account, f"COGS Vendor Bill - {category_name} - {expense_account.name}",
            amount, 0.0, analytics
        )
        lines.append((0, 0, expense_line))

        return lines

    def _create_line_data(self, account, name, debit, credit, analytics):
        """Create journal line data dictionary"""
        line_data = {
            'account_id': account.id,
            'display_type': self.COGS_DISPLAY_TYPE,
            'name': name,
            'debit': debit,
            'credit': credit,
            'partner_id': self.partner_id.id,
            'move_id': self.id,
        }

        if analytics:
            line_data['analytic_distribution'] = analytics

        return line_data

    def _apply_cogs_lines(self, new_lines, bop_amounts, bill_amount):
        """Apply COGS lines to the move and post message"""
        _logger.info(f"COGS DEBUG => Detail Line IDS => {new_lines}")
        self.write({'line_ids': new_lines})
        _logger.info("COGS DEBUG => Successfully updated line_ids")

        # Create success message
        message_parts = []
        if bop_amounts and len(bop_amounts) > 0:
            total_bop = sum(bop_amounts) if isinstance(bop_amounts, list) else bop_amounts
            message_parts.append(f"Highest BOP: {total_bop:,.2f}")
        if bill_amount > 0:
            message_parts.append(f"Vendor Bill: {bill_amount:,.2f}")

        total_bop_amount = sum(bop_amounts) if isinstance(bop_amounts, list) and bop_amounts else 0
        total_amount = total_bop_amount + (bill_amount if bill_amount else 0)
        message = (f"COGS Journal items telah ditambahkan otomatis dengan analytic distribution terpisah "
                   f"({', '.join(message_parts)}, Total: {total_amount:,.2f})")

        self.message_post(body=message)
        _logger.info("COGS DEBUG => Posted success message")

    def action_post(self):
        """Override action_post - COGS items are created on save, not on post"""
        return super().action_post()