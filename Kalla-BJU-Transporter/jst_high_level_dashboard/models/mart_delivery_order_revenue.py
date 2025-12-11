from odoo import models, fields, api
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class MartDeliveryOrderRevenue(models.Model):
    _name = 'mart.delivery.order.revenue'
    _description = 'Delivery Order Revenue Data Mart'
    _order = 'date desc, do_id'

    do_id = fields.Integer('Delivery Order ID', required=True, index=True)
    date = fields.Date('Date', required=True, index=True)
    status_do = fields.Char('Status DO', size=50)
    status_do_capitalize = fields.Char('Status DO Capitalized', size=50)
    partner_name = fields.Char('Partner Name', size=255)
    order_revenue = fields.Float('Order Revenue', digits=(16, 2), default=0.0)
    order_bop = fields.Float('Order BOP', digits=(16, 2), default=0.0)

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart records from the SQL query.

        Args:
            bulan_ini_only (bool): If True, only process current month data
        """
        try:
            # Get current month and year
            today = date.today()
            current_month = today.month
            current_year = today.year

            # If bulan_ini_only is True, delete current month data first
            if bulan_ini_only:
                _logger.info("Deleting current month data mart records...")
                domain = [
                    ('date', '>=', date(current_year, current_month, 1)),
                    ('date', '<', date(current_year, current_month + 1, 1) if current_month < 12
                    else date(current_year + 1, 1, 1))
                ]
                current_month_records = self.search(domain)
                current_month_records.unlink()
                _logger.info(f"Deleted {len(current_month_records)} current month records")

            # Build the SQL query
            base_query = """
                SELECT
                    fd.id as do_id,
                    fd.date,
                    fd.status_do,
                    UPPER(fd.status_do) AS status_do_capitalize,
                    rp.name as partner_name,
                    COALESCE(SUM(sol.price_unit), 0) AS order_revenue,
                    COALESCE(MAX(sol.bop), 0) AS order_bop
                FROM
                    sale_order_line sol
                INNER JOIN fleet_do fd ON fd.id = sol.do_id
                INNER JOIN res_partner rp ON rp.id = sol.order_partner_id
                WHERE
                    fd.date IS NOT NULL
            """

            # Add month filter if bulan_ini_only is True
            if bulan_ini_only:
                base_query += f"""
                    AND EXTRACT(YEAR FROM fd.date) = {current_year}
                    AND EXTRACT(MONTH FROM fd.date) = {current_month}
                """

            base_query += """
                GROUP BY
                    fd.id,
                    fd.date,
                    fd.status_do,
                    rp.name
                ORDER BY
                    EXTRACT(YEAR FROM fd.date) DESC,
                    EXTRACT(MONTH FROM fd.date) ASC
            """

            # Execute the query
            _logger.info(f"Executing data mart query (bulan_ini_only={bulan_ini_only})...")
            self.env.cr.execute(base_query)
            results = self.env.cr.fetchall()

            # Prepare data for batch insert
            data_to_insert = []
            for row in results:
                data_to_insert.append({
                    'do_id': row[0],
                    'date': row[1],
                    'status_do': row[2],
                    'status_do_capitalize': row[3],
                    'partner_name': row[4],
                    'order_revenue': float(row[5]) if row[5] else 0.0,
                    'order_bop': float(row[6]) if row[6] else 0.0,
                })

            # Batch create records
            if data_to_insert:
                self.create(data_to_insert)
                _logger.info(f"Successfully created {len(data_to_insert)} data mart records")
            else:
                _logger.info("No data found to insert into data mart")

            return True

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            return False

    @api.model
    def cron_generate_data_mart(self):
        """
        Scheduled method to generate/update data mart.
        This method is called by the cron job.
        """
        try:
            _logger.info("Starting scheduled data mart generation...")

            # Check if table is empty
            record_count = self.search_count([])

            if record_count == 0:
                # Table is empty, generate all data
                _logger.info("Data mart table is empty, generating all data...")
                result = self.generate_data_mart(bulan_ini_only=False)
            else:
                # Table has data, update current month only
                _logger.info("Data mart table has data, updating current month only...")
                result = self.generate_data_mart(bulan_ini_only=True)

            if result:
                _logger.info("Scheduled data mart generation completed successfully")
            else:
                _logger.error("Scheduled data mart generation failed")

        except Exception as e:
            _logger.error(f"Error in scheduled data mart generation: {str(e)}")

    @api.model
    def refresh_all_data(self):
        """
        Manual method to refresh all data mart records.
        This will delete all existing records and regenerate from scratch.
        """
        try:
            _logger.info("Starting manual refresh of all data mart records...")

            # Delete all existing records
            all_records = self.search([])
            all_records.unlink()
            _logger.info(f"Deleted {len(all_records)} existing records")

            # Generate all data
            result = self.generate_data_mart(bulan_ini_only=False)

            if result:
                _logger.info("Manual refresh completed successfully")
            else:
                _logger.error("Manual refresh failed")

            return result

        except Exception as e:
            _logger.error(f"Error in manual refresh: {str(e)}")
            return False