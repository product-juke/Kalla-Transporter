# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class MartBranchPerformance(models.Model):
    _name = 'mart.branch.performance'
    _description = 'Branch Performance Data Mart'
    _order = 'order_id desc, date_order desc'

    # Fields from query result
    company_id = fields.Integer(string='Company', readonly=True)
    company_parent_id = fields.Integer(string='Parent Company', readonly=True)
    company_parent_path = fields.Char(string='Company Parent Path', readonly=True)
    company_name = fields.Char(string='Company Name', readonly=True)
    order_id = fields.Integer(string='Sale Order', readonly=True)
    date_order = fields.Datetime(string='Order Date', readonly=True)
    order_line_id = fields.Integer(string='Order Line', readonly=True)
    distance = fields.Float(string='Distance', readonly=True)
    util_count = fields.Float(string='Util Count', readonly=True)
    revenue = fields.Float(string='Revenue', readonly=True)
    bop = fields.Float(string='BOP', readonly=True)

    def init(self):
        """Create the view/table for the data mart"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        # We don't create a view here since we're managing data manually

    @api.model
    def create_table_if_not_exists(self):
        """Create the physical table if it doesn't exist"""
        self.env.cr.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES res_company(id),
                company_parent_id INTEGER REFERENCES res_company(id),
                company_parent_path VARCHAR,
                company_name VARCHAR,
                order_id INTEGER REFERENCES sale_order(id),
                date_order TIMESTAMP,
                order_line_id INTEGER REFERENCES sale_order_line(id),
                distance NUMERIC,
                util_count NUMERIC DEFAULT 0,
                revenue NUMERIC DEFAULT 0,
                bop NUMERIC,
                create_date TIMESTAMP DEFAULT NOW(),
                write_date TIMESTAMP DEFAULT NOW(),
                create_uid INTEGER REFERENCES res_users(id),
                write_uid INTEGER REFERENCES res_users(id)
            )
        """)

        # Create indexes for better performance
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self._table}_company_id 
            ON {self._table}(company_id)
        """)
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self._table}_date_order 
            ON {self._table}(date_order)
        """)
        self.env.cr.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self._table}_order_id 
            ON {self._table}(order_id)
        """)

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart records
        Args:
            bulan_ini_only (bool): If True, only regenerate current month data
        """
        try:
            # Ensure table exists
            self.create_table_if_not_exists()

            # Check if table is empty
            self.env.cr.execute(f"SELECT COUNT(*) FROM {self._table}")
            record_count = self.env.cr.fetchone()[0]

            if record_count == 0:
                # Table is empty, generate all data
                _logger.info("Data mart table is empty, generating all data")
                self._generate_all_data()
            elif bulan_ini_only:
                # Delete current month data and regenerate
                _logger.info("Regenerating current month data")
                self._delete_current_month_data()
                self._generate_current_month_data()
            else:
                # Generate all data (full refresh)
                _logger.info("Full refresh of data mart")
                self._truncate_table()
                self._generate_all_data()

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            raise UserError(_("Error generating data mart: %s") % str(e))

    def _generate_all_data(self):
        """Generate all data from the main query"""
        query = """
            INSERT INTO mart_branch_performance 
            (company_id, company_parent_id, company_parent_path, company_name, 
             order_id, date_order, order_line_id, distance, util_count, revenue, bop,
             create_date, write_date, create_uid, write_uid)
            SELECT
                rc.id as company_id,
                rc.parent_id as company_parent_id,
                rc.parent_path as company_parent_path,
                rc.name as company_name,
                so.id as order_id,
                so.date_order as date_order,
                sol.id as order_line_id,
                sol.distance,
                coalesce(sum(sol.sla), 0) as util_count,
                coalesce(sum(sol.price_unit), 0) as revenue,
                (
                    case 
                        when sol.distance is not null then max(sol.bop)
                        else null
                    end
                ) as bop,
                NOW() as create_date,
                NOW() as write_date,
                %s as create_uid,
                %s as write_uid
            FROM res_company rc
            INNER JOIN sale_order so ON UPPER(so.branch_project) = UPPER(rc.company_code) 
            INNER JOIN sale_order_line sol ON sol.order_id = so.id
            GROUP BY rc.id, so.id, sol.id
        """

        self.env.cr.execute(query, (self.env.uid, self.env.uid))
        _logger.info(f"Generated {self.env.cr.rowcount} records in data mart")

    def _generate_current_month_data(self):
        """Generate data for current month only"""
        current_month_start = date.today().replace(day=1)

        query = """
            INSERT INTO mart_branch_performance 
            (company_id, company_parent_id, company_parent_path, company_name, 
             order_id, date_order, order_line_id, distance, util_count, revenue, bop,
             create_date, write_date, create_uid, write_uid)
            SELECT
                rc.id as company_id,
                rc.parent_id as company_parent_id,
                rc.parent_path as company_parent_path,
                rc.name as company_name,
                so.id as order_id,
                so.date_order as date_order,
                sol.id as order_line_id,
                sol.distance,
                coalesce(sum(sol.sla), 0) as util_count,
                coalesce(sum(sol.price_unit), 0) as revenue,
                (
                    case 
                        when sol.distance is not null then max(sol.bop)
                        else null
                    end
                ) as bop,
                NOW() as create_date,
                NOW() as write_date,
                %s as create_uid,
                %s as write_uid
            FROM res_company rc
            INNER JOIN sale_order so ON UPPER(so.branch_project) = UPPER(rc.company_code) 
            INNER JOIN sale_order_line sol ON sol.order_id = so.id
            WHERE DATE(so.date_order) >= %s
            GROUP BY rc.id, so.id, sol.id
        """

        self.env.cr.execute(query, (self.env.uid, self.env.uid, current_month_start))
        _logger.info(f"Generated {self.env.cr.rowcount} records for current month")

    def _delete_current_month_data(self):
        """Delete data for current month"""
        current_month_start = date.today().replace(day=1)

        query = f"""
            DELETE FROM {self._table} 
            WHERE DATE(date_order) >= %s
        """

        self.env.cr.execute(query, (current_month_start,))
        _logger.info(f"Deleted {self.env.cr.rowcount} records for current month")

    def _truncate_table(self):
        """Truncate the data mart table"""
        self.env.cr.execute(f"TRUNCATE TABLE {self._table} RESTART IDENTITY")
        _logger.info("Truncated data mart table")

    @api.model
    def cron_generate_data_mart(self):
        """Cron job method for scheduled data generation"""
        try:
            _logger.info("Starting scheduled data mart generation")

            # Ensure table exists
            self.create_table_if_not_exists()

            # Check if table is empty
            self.env.cr.execute(f"SELECT COUNT(*) FROM {self._table}")
            record_count = self.env.cr.fetchone()[0]

            if record_count == 0:
                # Table is empty, generate all data
                self.generate_data_mart(bulan_ini_only=False)
            else:
                # Table has data, regenerate current month only
                self.generate_data_mart(bulan_ini_only=True)

            _logger.info("Scheduled data mart generation completed successfully")

        except Exception as e:
            _logger.error(f"Error in scheduled data mart generation: {str(e)}")
            # Don't raise the exception to avoid breaking the cron job

    @api.model
    def action_manual_refresh(self):
        """Manual refresh action"""
        self.generate_data_mart(bulan_ini_only=False)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Data mart has been refreshed successfully'),
                'type': 'success',
            }
        }

    @api.model
    def action_refresh_current_month(self):
        """Refresh current month data action"""
        self.generate_data_mart(bulan_ini_only=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Current month data has been refreshed successfully'),
                'type': 'success',
            }
        }