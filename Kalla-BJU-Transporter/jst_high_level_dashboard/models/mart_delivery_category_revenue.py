from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class MartDeliveryCategoryRevenue(models.Model):
    _name = 'mart.delivery.category.revenue'
    _description = 'Data Mart - Delivery Category Revenue'
    _order = 'date desc, delivery_category_name asc'

    # Fields based on the SQL query result
    do_id = fields.Integer(string='Delivery Order ID', readonly=True)
    delivery_category_id = fields.Integer(string='Delivery Category ID', readonly=True)
    delivery_category_name = fields.Char(string='Category Name', readonly=True)
    name_capitalize = fields.Char(string='Category Name (Uppercase)', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    actual_revenue = fields.Float(string='Actual Revenue', readonly=True)
    bop = fields.Float(string='BOP', readonly=True)

    # Optional: Add Many2one fields for reference (but not required for data mart)
    fleet_do_ref = fields.Many2one('fleet.do', string='Delivery Order Ref', compute='_compute_references', store=False)
    delivery_category_ref = fields.Many2one('delivery.category', string='Category Ref', compute='_compute_references',
                                            store=False)

    @api.depends('do_id', 'delivery_category_id')
    def _compute_references(self):
        """Compute reference fields for Many2one relations"""
        for record in self:
            # Only set if the referenced record exists
            if record.do_id:
                fleet_do = self.env['fleet.do'].browse(record.do_id).exists()
                record.fleet_do_ref = fleet_do.id if fleet_do else False
            else:
                record.fleet_do_ref = False

            if record.delivery_category_id:
                delivery_cat = self.env['delivery.category'].browse(record.delivery_category_id).exists()
                record.delivery_category_ref = delivery_cat.id if delivery_cat else False
            else:
                record.delivery_category_ref = False

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart from the SQL query using ORM
        Args:
            bulan_ini_only (bool): If True, only regenerate current month data
        """
        try:
            current_date = fields.Date.today()
            current_month = current_date.month
            current_year = current_date.year

            # Check if table has data
            record_count = self.search_count([])

            if bulan_ini_only or (record_count > 0):
                # Delete current month data using ORM
                current_month_records = self.search([
                    ('date', '>=', f'{current_year}-{current_month:02d}-01'),
                    ('date', '<',
                     f'{current_year}-{current_month + 1:02d}-01' if current_month < 12 else f'{current_year + 1}-01-01')
                ])
                current_month_records.unlink()
                _logger.info(f"Deleted {len(current_month_records)} current month records")

                # Set date filter for current month only
                date_domain = [
                    ('date', '>=', f'{current_year}-{current_month:02d}-01'),
                    ('date', '<',
                     f'{current_year}-{current_month + 1:02d}-01' if current_month < 12 else f'{current_year + 1}-01-01')
                ]
            else:
                # Generate all data (empty table)
                date_domain = []
                _logger.info("Generating all data")

            # Get data using raw SQL query for aggregation (ORM doesn't handle complex aggregations well)
            where_condition = ""
            if date_domain:
                where_condition = f"AND EXTRACT(MONTH FROM fd.date) = {current_month} AND EXTRACT(YEAR FROM fd.date) = {current_year}"

            query = f"""
                SELECT
                    fd.id as do_id,
                    dc.id as delivery_category_id,
                    dc."name" as delivery_category_name,
                    UPPER(dc."name") as name_capitalize,
                    fd.date,
                    sum(sol.price_unit) as actual_revenue,
                    coalesce(max(sol.bop), 0) as bop
                FROM
                    fleet_do fd
                INNER JOIN sale_order_line sol ON sol.do_id = fd.id
                INNER JOIN delivery_category dc ON dc.id = fd.delivery_category_id 
                WHERE fd.date IS NOT NULL {where_condition}
                GROUP BY fd.id, dc.id, dc."name", fd."date"
                ORDER BY extract(year from fd.date) DESC, extract(month from fd.date) ASC
            """

            self.env.cr.execute(query)
            query_results = self.env.cr.fetchall()

            # Create records using ORM
            records_to_create = []
            for row in query_results:
                records_to_create.append({
                    'do_id': row[0],
                    'delivery_category_id': row[1],
                    'delivery_category_name': row[2],
                    'name_capitalize': row[3],
                    'date': row[4],
                    'actual_revenue': float(row[5]) if row[5] else 0.0,
                    'bop': float(row[6]) if row[6] else 0.0,
                })

            if records_to_create:
                self.create(records_to_create)
                _logger.info(f"Data mart generated successfully. {len(records_to_create)} records created.")
            else:
                _logger.info("No data to generate for data mart.")

            return {
                'success': True,
                'message': f'Data mart generated successfully. {len(records_to_create)} records processed.',
                'records_count': len(records_to_create)
            }

        except Exception as e:
            error_msg = f"Error generating data mart: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg)

    @api.model
    def cron_generate_data_mart(self):
        """
        Cron job method to automatically generate/update data mart
        """
        try:
            # Check if table has data
            record_count = self.search_count([])

            if record_count == 0:
                # Generate all data if table is empty
                result = self.generate_data_mart(bulan_ini_only=False)
                _logger.info("Cron: Generated all data mart records (table was empty)")
            else:
                # Update current month data only
                result = self.generate_data_mart(bulan_ini_only=True)
                _logger.info("Cron: Updated current month data mart records")

            return result

        except Exception as e:
            error_msg = f"Cron job failed: {str(e)}"
            _logger.error(error_msg)
            # Don't raise exception in cron to avoid stopping the scheduler
            return {'success': False, 'message': error_msg}

    @api.model
    def manual_refresh_all(self):
        """
        Manual method to refresh all data
        """
        # Clear all data first using ORM
        all_records = self.search([])
        all_records.unlink()
        return self.generate_data_mart(bulan_ini_only=False)

    @api.model
    def manual_refresh_current_month(self):
        """
        Manual method to refresh current month data only
        """
        return self.generate_data_mart(bulan_ini_only=True)

    def name_get(self):
        """Custom name_get method"""
        result = []
        for record in self:
            name = f"{record.delivery_category_name} - {record.date}"
            result.append((record.id, name))
        return result