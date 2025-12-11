# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class MartRevenueByUnit(models.Model):
    _name = 'mart.revenue.by.unit'
    _description = 'Mart Revenue By Unit'
    _order = 'year_of_order desc, month_of_order desc, order_date desc'

    # Fields berdasarkan query SELECT
    product_category_name = fields.Char(string='PRODUCT', required=True)
    model_category_name = fields.Char(string='JENIS UNIT', required=True)
    vehicle_name = fields.Char(string='Vehicle Name', required=True)
    license_plate = fields.Char(string='NOPOL', required=True)
    year_of_order = fields.Integer(string='Year of Order', required=True)
    month_of_order = fields.Integer(string='Month of Order', required=True)
    month_name_of_order = fields.Char(string='Month Name of Order', required=True)
    day_of_order = fields.Integer(string='Day of Order', required=True)
    actual_revenue = fields.Float(string='REVENUE', default=0.0)
    target_revenue = fields.Float(string='TARGET REVENUE', default=0.0)
    revenue_gap = fields.Float(string='SELISIH REV.', default=0.0)
    revenue_percentage = fields.Float(string='% ACV. REVENUE', default=0.0)
    max_distance_of_bop = fields.Float(string='Max Distance of BOP', default=0.0)
    total_bop = fields.Float(string='BOP', default=0.0)
    bop_to_rev_percentage = fields.Float(string='BOP. TO REV.', default=0.0)

    # New fields from updated query
    order_date = fields.Date(string='Order Date', required=True)
    total_day_utilize = fields.Integer(string='UTI. (Days)', default=0)

    # Additional fields untuk tracking
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)
    updated_date = fields.Datetime(string='Updated Date', default=fields.Datetime.now)

    @api.model
    def refresh_mart_data(self):
        """
        Method untuk refresh data mart revenue by unit
        - Jika data kosong: insert semua data dari query
        - Jika ada data: hapus data bulan/tahun ini, insert data baru bulan/tahun ini
        """
        try:
            _logger.info("Starting mart revenue by unit refresh process...")

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

            _logger.info("Mart revenue by unit refresh process completed successfully.")

        except Exception as e:
            _logger.error(f"Error in refresh_mart_data: {str(e)}")
            raise

    def _insert_all_data_from_query(self):
        """Insert semua data dari query ke dalam model"""
        query = """
        SELECT
            pc.name AS product_category_name,
            fvmc.name AS model_category_name,
            fv.name AS vehicle_name,
            fv.license_plate,
            EXTRACT(YEAR FROM fd.date) AS year_of_order,
            EXTRACT(MONTH FROM fd.date) AS month_of_order,
            TO_CHAR(fd.date, 'TMMonth') AS month_name_of_order,
            COALESCE(SUM(sol.price_unit), 0) AS actual_revenue,
            COALESCE(SUM(vtl.total_target), 0) AS target_revenue,
            COALESCE(SUM(sol.price_unit), 0) - COALESCE(SUM(vtl.total_target), 0) AS revenue_gap,
            CASE
                WHEN SUM(vtl.total_target) = 0 THEN 0
                ELSE COALESCE(ROUND(SUM(sol.price_unit) / SUM(vtl.total_target) * 100, 2), 0)
            END AS revenue_percentage,
            MAX(sol.distance) as max_distance_of_bop,
            COALESCE(SUM(sol.bop), 0) as total_bop,
            CASE
                WHEN SUM(sol.price_unit) = 0 THEN 0
                ELSE COALESCE(ROUND(SUM(sol.bop) / SUM(sol.price_unit) * 100, 2), 0)
            END AS bop_to_rev_percentage,
            fd.date as order_date,
            (
                SELECT COUNT(DISTINCT mvu.date)
                FROM mart_vehicle_utilization mvu
                WHERE
                    mvu.license_plate = fv.license_plate
                    AND mvu.status = 'UTILIZATION'
                    AND EXTRACT(YEAR FROM mvu.date) = EXTRACT(YEAR FROM fd.date)
                    AND EXTRACT(MONTH FROM mvu.date) = EXTRACT(MONTH FROM fd.date)
            ) AS total_day_utilize,
            EXTRACT(DAY FROM fd.date) AS day_of_order
        FROM
            fleet_do fd
        JOIN
            do_po_line_rel dplr ON fd.id = dplr.do_id
        JOIN
            sale_order_line sol ON sol.id = dplr.po_line_id
        JOIN
            fleet_vehicle fv ON fv.id = fd.vehicle_id
        JOIN
            fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id
        JOIN
            product_category pc ON pc.id = fv.product_category_id
        LEFT JOIN
            vehicle_target_line vtl ON vtl.month = EXTRACT(MONTH FROM fd.date) AND vtl.year = EXTRACT(YEAR FROM fd.date)
        WHERE
            fd.date IS NOT NULL
        GROUP BY
            fd.id,
            fv.name,
            fv.license_plate,
            EXTRACT(YEAR FROM fd.date),
            EXTRACT(MONTH FROM fd.date),
            EXTRACT(DAY FROM fd.date),
            TO_CHAR(fd.date, 'TMMonth'),
            pc.name,
            fvmc.name
        ORDER BY
            EXTRACT(YEAR FROM fd.date), EXTRACT(MONTH FROM fd.date) DESC
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure order_date is not None
            if row[14] is None:
                _logger.warning(f"Skipping row with null order_date: {row}")
                continue

            mart_data.append({
                'product_category_name': row[0] or '',
                'model_category_name': row[1] or '',
                'vehicle_name': row[2] or '',
                'license_plate': row[3] or '',
                'year_of_order': int(row[4]) if row[4] else 0,
                'month_of_order': int(row[5]) if row[5] else 0,
                'month_name_of_order': row[6] or '',
                'actual_revenue': float(row[7]) if row[7] else 0.0,
                'target_revenue': float(row[8]) if row[8] else 0.0,
                'revenue_gap': float(row[9]) if row[9] else 0.0,
                'revenue_percentage': float(row[10]) if row[10] else 0.0,
                'max_distance_of_bop': float(row[11]) if row[11] else 0.0,
                'total_bop': float(row[12]) if row[12] else 0.0,
                'bop_to_rev_percentage': float(row[13]) if row[13] else 0.0,
                'order_date': row[14],  # Now guaranteed to be not None
                'total_day_utilize': int(row[15]) if row[15] else 0,
                'day_of_order': int(row[16]) if row[16] else 0,
            })

        # Batch create untuk performa yang lebih baik
        if mart_data:
            self.create(mart_data)
            _logger.info(f"Inserted {len(mart_data)} records into mart.revenue.by.unit")

    def _refresh_current_month_data(self, year, month):
        """Hapus data bulan/tahun ini dan insert yang baru"""
        # Hapus data untuk bulan dan tahun ini
        records_to_delete = self.search([
            ('year_of_order', '=', year),
            ('month_of_order', '=', month)
        ])

        if records_to_delete:
            records_to_delete.unlink()
            _logger.info(f"Deleted {len(records_to_delete)} records for {month}/{year}")

        # Insert data baru untuk bulan dan tahun ini
        query = """
        SELECT
            pc.name AS product_category_name,
            fvmc.name AS model_category_name,
            fv.name AS vehicle_name,
            fv.license_plate,
            EXTRACT(YEAR FROM fd.date) AS year_of_order,
            EXTRACT(MONTH FROM fd.date) AS month_of_order,
            TO_CHAR(fd.date, 'TMMonth') AS month_name_of_order,
            COALESCE(SUM(sol.price_unit), 0) AS actual_revenue,
            COALESCE(SUM(vtl.total_target), 0) AS target_revenue,
            COALESCE(SUM(sol.price_unit), 0) - COALESCE(SUM(vtl.total_target), 0) AS revenue_gap,
            CASE
                WHEN SUM(vtl.total_target) = 0 THEN 0
                ELSE COALESCE(ROUND(SUM(sol.price_unit) / SUM(vtl.total_target) * 100, 2), 0)
            END AS revenue_percentage,
            MAX(sol.distance) as max_distance_of_bop,
            COALESCE(SUM(sol.bop), 0) as total_bop,
            CASE
                WHEN SUM(sol.price_unit) = 0 THEN 0
                ELSE COALESCE(ROUND(SUM(sol.bop) / SUM(sol.price_unit) * 100, 2), 0)
            END AS bop_to_rev_percentage,
            fd.date as order_date,
            (
                SELECT COUNT(DISTINCT mvu.date)
                FROM mart_vehicle_utilization mvu
                WHERE
                    mvu.license_plate = fv.license_plate
                    AND mvu.status = 'UTILIZATION'
                    AND EXTRACT(YEAR FROM mvu.date) = EXTRACT(YEAR FROM fd.date)
                    AND EXTRACT(MONTH FROM mvu.date) = EXTRACT(MONTH FROM fd.date)
            ) AS total_day_utilize,
            EXTRACT(DAY FROM fd.date) AS day_of_order
        FROM
            fleet_do fd
        JOIN
            do_po_line_rel dplr ON fd.id = dplr.do_id
        JOIN
            sale_order_line sol ON sol.id = dplr.po_line_id
        JOIN
            fleet_vehicle fv ON fv.id = fd.vehicle_id
        JOIN
            fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id
        JOIN
            product_category pc ON pc.id = fv.product_category_id
        LEFT JOIN
            vehicle_target_line vtl ON vtl.month = EXTRACT(MONTH FROM fd.date) AND vtl.year = EXTRACT(YEAR FROM fd.date)
        WHERE
            EXTRACT(YEAR FROM fd.date) = %s
            AND EXTRACT(MONTH FROM fd.date) = %s
            AND fd.date IS NOT NULL
        GROUP BY
            fd.id,
            fv.name,
            fv.license_plate,
            EXTRACT(YEAR FROM fd.date),
            EXTRACT(MONTH FROM fd.date),
            EXTRACT(DAY FROM fd.date),
            TO_CHAR(fd.date, 'TMMonth'),
            pc.name,
            fvmc.name
        ORDER BY
            EXTRACT(YEAR FROM fd.date), EXTRACT(MONTH FROM fd.date) DESC
        """

        self.env.cr.execute(query, (year, month))
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure order_date is not None
            if row[14] is None:
                _logger.warning(f"Skipping row with null order_date: {row}")
                continue

            mart_data.append({
                'product_category_name': row[0] or '',
                'model_category_name': row[1] or '',
                'vehicle_name': row[2] or '',
                'license_plate': row[3] or '',
                'year_of_order': int(row[4]) if row[4] else 0,
                'month_of_order': int(row[5]) if row[5] else 0,
                'month_name_of_order': row[6] or '',
                'actual_revenue': float(row[7]) if row[7] else 0.0,
                'target_revenue': float(row[8]) if row[8] else 0.0,
                'revenue_gap': float(row[9]) if row[9] else 0.0,
                'revenue_percentage': float(row[10]) if row[10] else 0.0,
                'max_distance_of_bop': float(row[11]) if row[11] else 0.0,
                'total_bop': float(row[12]) if row[12] else 0.0,
                'bop_to_rev_percentage': float(row[13]) if row[13] else 0.0,
                'order_date': row[14],  # Now guaranteed to be not None
                'total_day_utilize': int(row[15]) if row[15] else 0,
                'day_of_order': int(row[16]) if row[16] else 0,
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
        return super(MartRevenueByUnit, self).write(vals)