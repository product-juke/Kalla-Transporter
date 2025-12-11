# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, date
import calendar
import logging

_logger = logging.getLogger(__name__)


class MartCustomerInvoice(models.Model):
    _name = 'mart.customer.invoice'
    _description = 'Customer Invoice Data Mart'
    _order = 'invoice_status desc, days_overdue desc, customer, invoice_date desc'
    _rec_name = 'customer'

    # Core fields from query
    invoice_id = fields.Many2one('account.move', string='Invoice', ondelete='cascade')
    customer_id = fields.Many2one('res.partner', string='Customer ID', ondelete='cascade')
    customer = fields.Char(string='Customer Name', index=True)
    revenue = fields.Float(string='Revenue', digits='Product Price')
    invoice_date = fields.Date(string='Invoice Date', index=True)
    invoice_date_due = fields.Date(string='Due Date')
    invoice_state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Invoice State')
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string='Payment State')

    # Computed fields from query
    invoice_status = fields.Char(string='Invoice Status', index=True)
    days_overdue = fields.Integer(string='Days Overdue')
    overdue_category = fields.Selection([
        ('N/A', 'N/A'),
        ('Current', 'Current'),
        ('1-30 Days', '1-30 Days'),
        ('31-60 Days', '31-60 Days'),
        ('61-90 Days', '61-90 Days'),
        ('Over 90 Days', 'Over 90 Days'),
    ], string='Overdue Category', index=True)
    is_invoicing_issue = fields.Boolean(string='Is Invoicing Issue')
    is_bad_debt_issue = fields.Boolean(string='Is Bad Debt Issue')
    status_indicator = fields.Char(string='Status Indicator')

    # Metadata
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart from SQL query

        Args:
            bulan_ini_only (bool): If True, only refresh current month data
        """
        _logger.info("Starting data mart generation. Current month only: %s", bulan_ini_only)

        # Get current month range
        today = date.today()
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])

        # Determine what to delete
        if bulan_ini_only:
            # Delete current month data only
            self.search([
                ('invoice_date', '>=', first_day),
                ('invoice_date', '<=', last_day)
            ]).unlink()
            _logger.info("Deleted current month data (%s to %s)", first_day, last_day)
        else:
            # Check if table is empty
            record_count = self.search_count([])
            if record_count == 0:
                _logger.info("Table is empty, generating all data")
            else:
                # Delete all data
                self.search([]).unlink()
                _logger.info("Deleted all existing data (%d records)", record_count)

        # Build the main SQL query
        sql_query = """
        SELECT 
            am.id as invoice_id,
            rp.id as customer_id,
            rp.name as customer,
            SUM(sol.price_unit) as revenue,
            am.invoice_date,
            am.invoice_date_due,
            am.state as invoice_state,
            am.payment_state,
            CASE 
                WHEN am.invoice_date_due IS NULL THEN 'No Due Date'
                WHEN am.payment_state = 'paid' THEN 'Paid'
                WHEN am.state != 'posted' THEN 'Not Posted'
                WHEN am.invoice_date_due < CURRENT_DATE THEN 'OVERDUE'
                WHEN am.invoice_date_due = CURRENT_DATE THEN 'DUE TODAY'
                WHEN am.invoice_date_due > CURRENT_DATE THEN 'Not Due Yet'
                ELSE 'Unknown'
            END as invoice_status,
            CASE 
                WHEN am.invoice_date_due IS NULL THEN NULL
                WHEN am.payment_state = 'paid' THEN 0
                WHEN am.state != 'posted' THEN NULL
                ELSE CURRENT_DATE - am.invoice_date_due 
            END as days_overdue,
            CASE 
                WHEN am.invoice_date_due IS NULL OR am.payment_state = 'paid' OR am.state != 'posted' THEN 'N/A'
                WHEN am.invoice_date_due >= CURRENT_DATE THEN 'Current'
                WHEN CURRENT_DATE - am.invoice_date_due <= 30 THEN '1-30 Days'
                WHEN CURRENT_DATE - am.invoice_date_due <= 60 THEN '31-60 Days'
                WHEN CURRENT_DATE - am.invoice_date_due <= 90 THEN '61-90 Days'
                ELSE 'Over 90 Days'
            END as overdue_category,
            CASE 
                WHEN am.invoice_date_due IS NOT NULL 
                     AND am.payment_state != 'paid' 
                     AND am.state = 'posted' 
                     AND am.invoice_date_due < CURRENT_DATE 
                THEN 1
                ELSE 0
            END as is_invoicing_issue,
            CASE 
                WHEN am.invoice_date_due IS NOT NULL 
                     AND am.payment_state != 'paid' 
                     AND am.state = 'posted' 
                     AND am.invoice_date_due < CURRENT_DATE 
                THEN 1
                ELSE 0
            END as is_bad_debt_issue,
            CASE 
                WHEN am.payment_state = 'paid' THEN '✅ Paid'
                WHEN am.state != 'posted' THEN '⏳ Draft/Cancel'
                WHEN am.invoice_date_due IS NULL THEN '⚠️ No Due Date'
                WHEN am.invoice_date_due < CURRENT_DATE THEN '🚨 OVERDUE'
                WHEN am.invoice_date_due = CURRENT_DATE THEN '⏰ Due Today'
                ELSE '✓ Current'
            END as status_indicator
        FROM 
            res_partner rp
        LEFT JOIN res_company rc ON 
            rc.id = rp.company_id
        INNER JOIN sale_order_line sol ON 
            sol.order_partner_id = rp.id
        INNER JOIN sale_order_line_invoice_rel solir ON 
            solir.order_line_id = sol.id
        INNER JOIN account_move_line aml ON 
            solir.invoice_line_id = aml.id
        INNER JOIN account_move am ON 
            am.id = aml.move_id
        WHERE 
            am.invoice_date IS NOT NULL
            AND (rp.is_vendor IS NULL OR rp.is_vendor = FALSE)
            AND (rp.is_driver IS NULL OR rp.is_driver = FALSE)
            AND rp.company_id IS NOT NULL
            AND (rc.name IS NULL OR LOWER(rc.name) NOT LIKE '%walls%')
        """

        # Add date filter for current month if needed
        if bulan_ini_only:
            sql_query += f"""
            AND am.invoice_date >= '{first_day}'
            AND am.invoice_date <= '{last_day}'
            """

        sql_query += """
        GROUP BY 
            rp.id,
            rp.name,
            am.id,
            am.invoice_date,
            am.invoice_date_due,
            am.state,
            am.payment_state
        ORDER BY 
            invoice_status DESC,
            days_overdue DESC,
            customer,
            invoice_date DESC
        """

        # Execute query
        self.env.cr.execute(sql_query)
        results = self.env.cr.dictfetchall()

        _logger.info("Retrieved %d records from query", len(results))

        # Insert data
        records_created = 0
        for row in results:
            try:
                # Handle None values for boolean fields
                is_invoicing_issue = bool(row.get('is_invoicing_issue', 0))
                is_bad_debt_issue = bool(row.get('is_bad_debt_issue', 0))

                # Create record
                self.create({
                    'invoice_id': row.get('invoice_id'),
                    'customer_id': row.get('customer_id'),
                    'customer': row.get('customer'),
                    'revenue': row.get('revenue', 0.0),
                    'invoice_date': row.get('invoice_date'),
                    'invoice_date_due': row.get('invoice_date_due'),
                    'invoice_state': row.get('invoice_state'),
                    'payment_state': row.get('payment_state'),
                    'invoice_status': row.get('invoice_status'),
                    'days_overdue': row.get('days_overdue'),
                    'overdue_category': row.get('overdue_category'),
                    'is_invoicing_issue': is_invoicing_issue,
                    'is_bad_debt_issue': is_bad_debt_issue,
                    'status_indicator': row.get('status_indicator'),
                })
                records_created += 1

            except Exception as e:
                _logger.error("Error creating record: %s", e)
                continue

        _logger.info("Data mart generation completed. Created %d records", records_created)
        return records_created

    @api.model
    def cron_refresh_data_mart(self):
        """
        Scheduled method for daily data mart refresh
        """
        _logger.info("Starting scheduled data mart refresh")

        # Check if table has data
        record_count = self.search_count([])

        if record_count == 0:
            # Table is empty, generate all data
            self.generate_data_mart(bulan_ini_only=False)
        else:
            # Table has data, refresh current month only
            self.generate_data_mart(bulan_ini_only=True)

        _logger.info("Scheduled data mart refresh completed")

    @api.model
    def manual_refresh_all(self):
        """
        Manual method to refresh all data
        """
        return self.generate_data_mart(bulan_ini_only=False)

    @api.model
    def manual_refresh_current_month(self):
        """
        Manual method to refresh current month data only
        """
        return self.generate_data_mart(bulan_ini_only=True)