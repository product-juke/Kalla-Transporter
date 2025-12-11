import logging
from datetime import datetime
from odoo import api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MartDeliveryOrder(models.Model):
    _name = 'mart.delivery.order'
    _description = 'Delivery Order Data Mart'
    _order = 'date asc'

    # Fields sesuai dengan hasil query SQL
    source_id = fields.Integer(string='Source ID', help='Original fleet_do record ID')
    name = fields.Char(string='Name', readonly=True)
    status_do = fields.Char(string='Status DO', readonly=True)
    status_do_capitalize = fields.Char(string='Status DO Capitalize', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    day_of_order = fields.Integer(string='Day of Order', readonly=True)
    month_of_order = fields.Integer(string='Month of Order', readonly=True)
    year_of_order = fields.Integer(string='Year of Order', readonly=True)

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate atau regenerate data mart

        Args:
            bulan_ini_only (bool): Jika True, hanya generate data bulan ini
        """
        try:
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year

            if bulan_ini_only:
                # Hapus data bulan ini
                self.search([
                    ('month_of_order', '=', current_month),
                    ('year_of_order', '=', current_year)
                ]).unlink()

                # Generate data bulan ini saja
                query = """
                    SELECT
                        fd.id,
                        fd.name,
                        fd.status_do,
                        UPPER(fd.status_do) AS status_do_capitalize,
                        fd.date,
                        EXTRACT(DAY FROM fd.date) AS day_of_order,
                        EXTRACT(MONTH FROM fd.date) AS month_of_order,
                        EXTRACT(YEAR FROM fd.date) AS year_of_order
                    FROM
                        fleet_do fd
                    WHERE
                        fd.date IS NOT NULL
                        AND EXTRACT(MONTH FROM fd.date) = %s
                        AND EXTRACT(YEAR FROM fd.date) = %s
                    ORDER BY
                        fd.date ASC;
                """
                self.env.cr.execute(query, (current_month, current_year))
                _logger.info(f"Regenerating data mart for month {current_month}/{current_year}")
            else:
                # Cek apakah tabel kosong
                existing_count = self.search_count([])
                if existing_count > 0:
                    _logger.info("Data mart already has data, skipping full regeneration")
                    return

                # Generate semua data
                query = """
                    SELECT
                        fd.id,
                        fd.name,
                        fd.status_do,
                        UPPER(fd.status_do) AS status_do_capitalize,
                        fd.date,
                        EXTRACT(DAY FROM fd.date) AS day_of_order,
                        EXTRACT(MONTH FROM fd.date) AS month_of_order,
                        EXTRACT(YEAR FROM fd.date) AS year_of_order
                    FROM
                        fleet_do fd
                    WHERE
                        fd.date IS NOT NULL
                    ORDER BY
                        fd.date ASC;
                """
                self.env.cr.execute(query)
                _logger.info("Generating full data mart from scratch")

            # Fetch hasil query dan insert ke data mart
            results = self.env.cr.fetchall()

            if not results:
                _logger.info("No data found to insert into data mart")
                return

            # Prepare data untuk batch insert
            values_list = []
            for row in results:
                values_list.append({
                    'source_id': row[0],
                    'name': row[1],
                    'status_do': row[2],
                    'status_do_capitalize': row[3],
                    'date': row[4],
                    'day_of_order': int(row[5]) if row[5] else 0,
                    'month_of_order': int(row[6]) if row[6] else 0,
                    'year_of_order': int(row[7]) if row[7] else 0,
                })

            # Batch create records
            if values_list:
                self.create(values_list)
                _logger.info(f"Successfully inserted {len(values_list)} records into data mart")

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            raise UserError(f"Failed to generate data mart: {str(e)}")

    @api.model
    def cron_update_data_mart(self):
        """
        Method untuk scheduler cron
        """
        try:
            existing_count = self.search_count([])

            if existing_count == 0:
                # Tabel kosong, generate semua data
                _logger.info("Data mart is empty, generating all data")
                self.generate_data_mart(bulan_ini_only=False)
            else:
                # Tabel sudah ada data, regenerate bulan ini
                _logger.info("Data mart has existing data, regenerating current month")
                self.generate_data_mart(bulan_ini_only=True)

        except Exception as e:
            _logger.error(f"Error in cron job: {str(e)}")
            raise

    def action_refresh_data_mart(self):
        """
        Action untuk manual refresh (bisa dipanggil dari UI)
        """
        self.generate_data_mart(bulan_ini_only=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Data mart has been refreshed successfully!',
                'type': 'success',
                'sticky': False,
            }
        }