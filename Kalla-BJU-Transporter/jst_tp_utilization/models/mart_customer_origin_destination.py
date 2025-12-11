# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class MartCustomerOriginDestination(models.Model):
    _name = 'mart.customer.origin.destination'
    _description = 'Mart Customer Origin Destination'
    _order = 'year_of_order desc, month_of_order desc'

    # Fields berdasarkan query SELECT
    customer_name = fields.Char(string='CUSTOMER', required=True)
    origin_name = fields.Char(string='ASAL')
    destination_name = fields.Char(string='TUJUAN')
    year_of_order = fields.Integer(string='Year of Order', required=True)
    month_of_order = fields.Integer(string='Month of Order', required=True)
    # month_name_of_order = fields.Char(string='Month Name of Order', required=True)
    order_date_formatted = fields.Date(string='Order Date', required=True)

    # Additional fields untuk tracking
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)
    updated_date = fields.Datetime(string='Updated Date', default=fields.Datetime.now)

    @api.model
    def refresh_mart_data(self):
        """
        Method untuk refresh data mart customer OD
        - Jika data kosong: insert semua data dari query
        - Jika ada data: hapus data bulan/tahun ini, insert data baru bulan/tahun ini
        """
        try:
            _logger.info("Starting mart customer OD refresh process...")

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

            _logger.info("Mart customer OD refresh process completed successfully.")

        except Exception as e:
            _logger.error(f"Error in refresh_mart_data: {str(e)}")
            raise

    def _insert_all_data_from_query(self):
        """Insert semua data dari query ke dalam model"""
        query = """
        select 
            a.customer_name, 
            a.origin_name, 
            a.destination_name, 
            a.year_of_order, 
            a.month_of_order,
            TO_CHAR(DATE_TRUNC('month', MAKE_DATE(a.year_of_order::int, a.month_of_order::int, 1)) + INTERVAL '1 month - 1 day', 'YYYY-MM-DD') as order_date_formatted
        from (
            SELECT
                fd.id,
                rp.name as customer_name,
                origin.name as origin_name,
                destination.name as destination_name,
                fd.date as order_date,
                EXTRACT(YEAR FROM fd.date) AS year_of_order,
                EXTRACT(MONTH FROM fd.date) AS month_of_order,
                TO_CHAR(fd.date, 'TMMonth') AS month_name_of_order,
                DATE_PART('day', (DATE_TRUNC('month', fd.date) + INTERVAL '1 month - 1 day')) AS total_days_in_month
            FROM
                fleet_do fd
            JOIN
                do_po_line_rel dplr ON fd.id = dplr.do_id
            JOIN
                sale_order_line sol ON sol.id = dplr.po_line_id
            join
                res_partner rp on rp.id = fd.partner_id
            JOIN
                fleet_vehicle fv ON fv.id = fd.vehicle_id
            LEFT JOIN LATERAL (
                SELECT mo.name as name
                FROM do_po_line_rel dplr2
                JOIN sale_order_line sol2 ON sol2.id = dplr2.po_line_id
                JOIN master_origin mo ON mo.id = sol2.origin_id
                WHERE dplr2.do_id = fd.id
                ORDER BY sol2.distance DESC
                LIMIT 1
            ) AS origin ON true
            LEFT JOIN LATERAL (
                SELECT mo.name as name
                FROM do_po_line_rel dplr3
                JOIN sale_order_line sol3 ON sol3.id = dplr3.po_line_id
                JOIN master_origin mo ON mo.id = sol3.destination_id
                WHERE dplr3.do_id = fd.id
                ORDER BY sol3.distance DESC
                LIMIT 1
            ) AS destination ON TRUE
            GROUP BY
                fd.id,
                EXTRACT(YEAR FROM fd.date),
                EXTRACT(MONTH FROM fd.date),
                rp.name,
                origin.name,
                destination.name
            ORDER BY
                EXTRACT(YEAR FROM fd.date), EXTRACT(MONTH FROM fd.date) DESC
        ) a 
        group by 1, 2, 3, 4, 5 
        order by 4, 5 ASC;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            mart_data.append({
                'customer_name': row[0] or '',
                'origin_name': row[1] or '',
                'destination_name': row[2] or '',
                'year_of_order': int(row[3]) if row[3] else 0,
                'month_of_order': int(row[4]) if row[4] else 0,
                'order_date_formatted': row[5] or '',
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
        select 
            a.customer_name, 
            a.origin_name, 
            a.destination_name, 
            a.year_of_order, 
            a.month_of_order,
            TO_CHAR(DATE_TRUNC('month', MAKE_DATE(a.year_of_order::int, a.month_of_order::int, 1)) + INTERVAL '1 month - 1 day', 'YYYY-MM-DD') as order_date_formatted
        from (
            SELECT
                fd.id,
                rp.name as customer_name,
                origin.name as origin_name,
                destination.name as destination_name,
                fd.date as order_date,
                EXTRACT(YEAR FROM fd.date) AS year_of_order,
                EXTRACT(MONTH FROM fd.date) AS month_of_order,
                TO_CHAR(fd.date, 'TMMonth') AS month_name_of_order,
                DATE_PART('day', (DATE_TRUNC('month', fd.date) + INTERVAL '1 month - 1 day')) AS total_days_in_month
            FROM
                fleet_do fd
            JOIN
                do_po_line_rel dplr ON fd.id = dplr.do_id
            JOIN
                sale_order_line sol ON sol.id = dplr.po_line_id
            join
                res_partner rp on rp.id = fd.partner_id
            JOIN
                fleet_vehicle fv ON fv.id = fd.vehicle_id
            LEFT JOIN LATERAL (
                SELECT mo.name as name
                FROM do_po_line_rel dplr2
                JOIN sale_order_line sol2 ON sol2.id = dplr2.po_line_id
                JOIN master_origin mo ON mo.id = sol2.origin_id
                WHERE dplr2.do_id = fd.id
                ORDER BY sol2.distance DESC
                LIMIT 1
            ) AS origin ON true
            LEFT JOIN LATERAL (
                SELECT mo.name as name
                FROM do_po_line_rel dplr3
                JOIN sale_order_line sol3 ON sol3.id = dplr3.po_line_id
                JOIN master_origin mo ON mo.id = sol3.destination_id
                WHERE dplr3.do_id = fd.id
                ORDER BY sol3.distance DESC
                LIMIT 1
            ) AS destination ON TRUE
            GROUP BY
                fd.id,
                EXTRACT(YEAR FROM fd.date),
                EXTRACT(MONTH FROM fd.date),
                rp.name,
                origin.name,
                destination.name
            ORDER BY
                EXTRACT(YEAR FROM fd.date), EXTRACT(MONTH FROM fd.date) DESC
        ) a 
        WHERE
            EXTRACT(YEAR FROM fd.date) = %s
            AND EXTRACT(MONTH FROM fd.date) = %s
        group by 1, 2, 3, 4, 5 
        order by 4, 5 ASC;
        """

        self.env.cr.execute(query, (year, month))
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            mart_data.append({
                'customer_name': row[0] or '',
                'origin_name': row[1] or '',
                'destination_name': row[2] or '',
                'year_of_order': int(row[3]) if row[3] else 0,
                'month_of_order': int(row[4]) if row[4] else 0,
                'month_name_of_order': str(row[5]) if row[5] else 0,
                'order_date_formatted': row[6] or '',
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
        return super(MartCustomerOriginDestination, self).write(vals)