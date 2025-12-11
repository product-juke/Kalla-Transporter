# -*- coding: utf-8 -*-
from email.policy import default

from odoo import models, fields, api
from datetime import datetime, date
import calendar
import logging

_logger = logging.getLogger(__name__)


class MartDailyPercentageSmry(models.Model):
    _name = 'mart.daily.percentage.smry'
    _description = 'Mart Daily Percentage Summary'

    # Fields berdasarkan query SELECT
    day = fields.Integer(string='DAY', required=True)
    total = fields.Integer(string='TOTAL', required=True, default=0)
    date = fields.Date(string='DATE', required=True)
    month = fields.Integer(string='MONTH', required=True)
    year = fields.Integer(string='YEAR', required=True)

    # Additional fields untuk tracking
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)
    updated_date = fields.Datetime(string='Updated Date', default=fields.Datetime.now)

    def _is_valid_date(self, year, month, day):
        """Validate if the date is valid"""
        try:
            year_int = int(year)
            month_int = int(month)
            day_int = int(day)

            # Check if the date is valid
            date(year_int, month_int, day_int)
            return True
        except (ValueError, TypeError):
            return False

    def _get_valid_date_string(self, year, month, day):
        """Get valid date string, handling invalid dates like Feb 29 in non-leap years"""
        try:
            year_int = int(year)
            month_int = int(month)
            day_int = int(day)

            # Check if date is valid
            if self._is_valid_date(year, month, day):
                return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
            else:
                # Handle invalid dates by adjusting to the last valid day of the month
                last_day = calendar.monthrange(year_int, month_int)[1]
                if day_int > last_day:
                    adjusted_day = last_day
                    _logger.warning(f"Invalid date {year}-{month}-{day}, adjusted to {year}-{month}-{adjusted_day}")
                    return f"{year}-{str(month).zfill(2)}-{str(adjusted_day).zfill(2)}"

        except (ValueError, TypeError) as e:
            _logger.error(f"Error creating date string for {year}-{month}-{day}: {str(e)}")
            return None

    @api.model
    def refresh_mart_data(self):
        """
        Method untuk refresh data mart revenue by unit
        - Jika data kosong: insert semua data dari query
        - Jika ada data: hapus data bulan/tahun ini, insert data baru bulan/tahun ini
        """
        try:
            _logger.info("Starting Mart Daily Percentage Summary refresh process...")

            current_date = datetime.now()
            current_year = current_date.year
            current_month = current_date.month

            # Check apakah data sudah ada
            existing_data = self.search([], limit=1)

            if not existing_data:
                # Data kosong, insert semua data
                _logger.info("No existing data found. Inserting all data from query...")
                self._insert_all_data_from_query()
            else:
                # Data sudah ada, hapus data bulan/tahun ini dan insert yang baru
                _logger.info(f"Existing data found. Refreshing data for {current_month}/{current_year}...")
                self._refresh_current_month_data(current_year, current_month)

            _logger.info("Mart Daily Percentage Summary refresh process completed successfully.")

        except Exception as e:
            _logger.error(f"Error in refresh_mart_data: {str(e)}")
            raise

    def _insert_all_data_from_query(self):
        """Insert semua data dari query ke dalam model"""
        query = """
        WITH unpivoted_data AS (
          SELECT 
            year,
            month,
            1 as day, day_1 as status FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 2, day_2 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 3, day_3 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 4, day_4 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 5, day_5 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 6, day_6 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 7, day_7 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 8, day_8 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 9, day_9 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 10, day_10 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 11, day_11 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 12, day_12 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 13, day_13 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 14, day_14 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 15, day_15 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 16, day_16 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 17, day_17 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 18, day_18 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 19, day_19 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 20, day_20 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 21, day_21 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 22, day_22 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 23, day_23 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 24, day_24 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 25, day_25 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 26, day_26 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 27, day_27 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 28, day_28 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 29, day_29 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 30, day_30 FROM mart_vehicle_utilization_daily_smry
          UNION ALL
          SELECT year, month, 31, day_31 FROM mart_vehicle_utilization_daily_smry
        )
        SELECT 
          year,
          month,
          day,
          COUNT(CASE WHEN status != 'BREAKDOWN' AND status IS NOT NULL THEN 1 END) as total,
          CONCAT(year, '-', LPAD(month, 2, '0')) as date_prefix
        FROM unpivoted_data
        GROUP BY day, year, month
        ORDER BY year, month, day;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure date components are not None
            if row[4] is None or row[0] is None or row[1] is None or row[2] is None:
                _logger.warning(f"Skipping row with null values: {row}")
                continue

            # Create valid date string with validation
            valid_date = self._get_valid_date_string(row[0], row[1], row[2])

            if valid_date is None:
                _logger.warning(f"Skipping row with invalid date: year={row[0]}, month={row[1]}, day={row[2]}")
                continue

            mart_data.append({
                'year': str(row[0]) if row[0] else '',
                'month': str(row[1]) if row[1] else '',
                'day': str(row[2]) if row[2] else '',
                'total': row[3] if row[3] is not None else 0,
                'date': valid_date,
            })

        # Batch create untuk performa yang lebih baik
        if mart_data:
            self.create(mart_data)
            _logger.info(f"Inserted {len(mart_data)} records into mart.daily.percentage.smry")

    def _refresh_current_month_data(self, year, month):
        """Hapus data bulan/tahun ini dan insert yang baru"""
        # Hapus data untuk bulan dan tahun ini
        records_to_delete = self.search([
            ('year', '=', str(year)),
            ('month', '=', str(month))
        ])

        if records_to_delete:
            records_to_delete.unlink()
            _logger.info(f"Deleted {len(records_to_delete)} records for {month}/{year}")

        # Insert data baru untuk bulan dan tahun ini
        query = """
            WITH unpivoted_data AS (
              SELECT 
                year,
                month,
                1 as day, day_1 as status FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 2, day_2 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 3, day_3 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 4, day_4 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 5, day_5 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 6, day_6 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 7, day_7 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 8, day_8 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 9, day_9 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 10, day_10 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 11, day_11 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 12, day_12 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 13, day_13 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 14, day_14 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 15, day_15 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 16, day_16 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 17, day_17 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 18, day_18 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 19, day_19 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 20, day_20 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 21, day_21 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 22, day_22 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 23, day_23 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 24, day_24 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 25, day_25 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 26, day_26 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 27, day_27 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 28, day_28 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 29, day_29 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 30, day_30 FROM mart_vehicle_utilization_daily_smry
              UNION ALL
              SELECT year, month, 31, day_31 FROM mart_vehicle_utilization_daily_smry
            )
            SELECT 
              year,
              month,
              day,
              COUNT(CASE WHEN status != 'BREAKDOWN' AND status IS NOT NULL THEN 1 END) as total,
              CONCAT(year, '-', LPAD(month, 2, '0')) as date_prefix
            FROM unpivoted_data
            WHERE
                year = %s
                AND month = %s
            GROUP BY day, year, month
            ORDER BY year, month, day;
        """

        self.env.cr.execute(query, (year, month))
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure date components are not None
            if row[4] is None or row[0] is None or row[1] is None or row[2] is None:
                _logger.warning(f"Skipping row with null values: {row}")
                continue

            # Create valid date string with validation
            valid_date = self._get_valid_date_string(row[0], row[1], row[2])

            if valid_date is None:
                _logger.warning(f"Skipping row with invalid date: year={row[0]}, month={row[1]}, day={row[2]}")
                continue

            mart_data.append({
                'year': str(row[0]) if row[0] else '',
                'month': str(row[1]) if row[1] else '',
                'day': str(row[2]) if row[2] else '',
                'total': row[3] if row[3] is not None else 0,
                'date': valid_date,
            })

        # Batch create untuk performa yang lebih baik
        if mart_data:
            self.create(mart_data)
            _logger.info(f"Inserted {len(mart_data)} new records for {month}/{year}")

    @api.model
    def manual_refresh(self):
        """Method untuk manual refresh (bisa dipanggil dari UI)"""
        return self.refresh_mart_data()

    def write(self, vals):
        """Override write untuk update timestamp"""
        vals['updated_date'] = fields.Datetime.now()
        return super(MartDailyPercentageSmry, self).write(vals)