# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class MartRevenueCustomerToUnit(models.Model):
    _name = 'mart.revenue.customer.to.unit'
    _description = 'Mart Revenue Customer to Unit'
    _order = 'year_of_order desc, month_of_order desc'

    # Fields berdasarkan query
    customer_name = fields.Char(string='CUSTOMER', required=True)
    actual_revenue = fields.Float(string='REVENUE', default=0.0)
    total_bop = fields.Float(string='BOP', default=0.0)
    bop_to_rev_percentage = fields.Float(string='BOP. TO. REV', default=0.0)
    year_of_order = fields.Integer(string='Year of Order', required=True)
    month_of_order = fields.Integer(string='Month of Order', required=True)
    month_name_of_order = fields.Char(string='Month Name of Order')
    total_days_in_month = fields.Integer(string='Total Days in Month', default=0)
    origin_name = fields.Char(string='ASAL')
    destination_name = fields.Char(string='TUJUAN')
    order_date = fields.Date(string='Order Date', required=True)

    # Field untuk tracking
    created_at = fields.Datetime(string='Created At', default=fields.Datetime.now)
    updated_at = fields.Datetime(string='Updated At', default=fields.Datetime.now)

    def write(self, vals):
        vals['updated_at'] = fields.Datetime.now()
        return super(MartRevenueCustomerToUnit, self).write(vals)

    @api.model
    def _get_revenue_data_query(self):
        """
        Query untuk mengambil data revenue customer
        """
        return """
            SELECT
                rp.name as customer_name,
                COALESCE(SUM(sol.price_unit), 0) AS actual_revenue,
                COALESCE(SUM(sol.bop), 0) as total_bop,
                CASE
                    WHEN SUM(sol.price_unit) = 0 THEN 0
                    ELSE COALESCE(ROUND(SUM(sol.bop) / SUM(sol.price_unit) * 100, 2), 0)
                END AS bop_to_rev_percentage,
                EXTRACT(YEAR FROM fd.date) AS year_of_order,
                EXTRACT(MONTH FROM fd.date) AS month_of_order,
                TO_CHAR(fd.date, 'TMMonth') AS month_name_of_order,
                DATE_PART('day', (DATE_TRUNC('month', fd.date) + INTERVAL '1 month - 1 day')) AS total_days_in_month,
                origin.name as origin_name,
                destination.name as destination_name,
                fd.date as order_date
            FROM
                fleet_do fd
            JOIN
                do_po_line_rel dplr ON fd.id = dplr.do_id
            JOIN
                sale_order_line sol ON sol.id = dplr.po_line_id
            JOIN
                res_partner rp ON rp.id = fd.partner_id
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
                rp.name,
                origin.name,
                destination.name
            ORDER BY
                EXTRACT(YEAR FROM fd.date), EXTRACT(MONTH FROM fd.date) DESC
        """

    @api.model
    def _execute_query(self, query):
        """
        Execute raw SQL query dan return hasilnya
        """
        try:
            # Commit any pending transactions first
            self.env.cr.commit()
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()
            return result
        except Exception as e:
            _logger.error(f"Error executing query: {str(e)}")
            # Rollback transaction on error
            self.env.cr.rollback()
            return []

    @api.model
    def _insert_data_from_query(self, data_list):
        """
        Insert data dari hasil query ke model
        """
        inserted_count = 0
        for data in data_list:
            try:
                # Konversi data sesuai dengan field model
                vals = {
                    'customer_name': data.get('customer_name', '') or '',
                    'actual_revenue': float(data.get('actual_revenue') or 0),
                    'total_bop': float(data.get('total_bop') or 0),
                    'bop_to_rev_percentage': float(data.get('bop_to_rev_percentage') or 0),
                    'year_of_order': int(data.get('year_of_order') or 0),
                    'month_of_order': int(data.get('month_of_order') or 0),
                    'month_name_of_order': data.get('month_name_of_order', '') or '',
                    'total_days_in_month': int(data.get('total_days_in_month') or 0),
                    'origin_name': data.get('origin_name', '') or '',
                    'destination_name': data.get('destination_name', '') or '',
                    'order_date': data.get('order_date'),
                }

                # Validate required fields
                if not vals['customer_name'] or not vals['order_date']:
                    _logger.warning(f"Skipping record with missing required fields: {data}")
                    continue

                self.create(vals)
                inserted_count += 1

            except Exception as e:
                _logger.error(f"Error inserting data: {str(e)}, Data: {data}")
                continue

        return inserted_count

    @api.model
    def _delete_current_month_data(self):
        """
        Hapus data untuk bulan dan tahun saat ini
        """
        try:
            now = datetime.now()
            current_year = now.year
            current_month = now.month

            # Hapus data untuk bulan dan tahun saat ini
            records_to_delete = self.search([
                ('year_of_order', '=', current_year),
                ('month_of_order', '=', current_month)
            ])

            if records_to_delete:
                count = len(records_to_delete)
                records_to_delete.unlink()
                _logger.info(f"Deleted {count} records for {current_month}/{current_year}")

        except Exception as e:
            _logger.error(f"Error deleting current month data: {str(e)}")
            raise

    @api.model
    def update_revenue_data(self):
        """
        Method utama untuk update data revenue
        Akan dijalankan oleh scheduler
        """
        try:
            _logger.info("Starting revenue data update process...")

            # Cek apakah model sudah ada data
            existing_records = self.search([])

            if not existing_records:
                # Jika tidak ada data, insert semua data dari query
                _logger.info("No existing data found. Inserting all data from query...")

                query = self._get_revenue_data_query()
                data_list = self._execute_query(query)

                if data_list:
                    inserted_count = self._insert_data_from_query(data_list)
                    _logger.info(f"Successfully inserted {inserted_count} records")
                else:
                    _logger.warning("No data returned from query")

            else:
                # Jika sudah ada data, hapus data bulan ini dan insert data baru
                _logger.info("Existing data found. Updating current month data...")

                # Hapus data bulan dan tahun saat ini
                self._delete_current_month_data()

                # Query untuk data bulan dan tahun saat ini saja
                now = datetime.now()
                current_year = now.year
                current_month = now.month

                # Build query dengan filter bulan dan tahun saat ini
                base_query = self._get_revenue_data_query()

                # Tambahkan WHERE clause untuk filter bulan dan tahun saat ini
                filtered_query = base_query.replace(
                    "ORDER BY",
                    f"HAVING EXTRACT(YEAR FROM fd.date) = {current_year} AND EXTRACT(MONTH FROM fd.date) = {current_month} ORDER BY"
                )

                data_list = self._execute_query(filtered_query)

                if data_list:
                    inserted_count = self._insert_data_from_query(data_list)
                    _logger.info(f"Successfully updated {inserted_count} records for {current_month}/{current_year}")
                else:
                    _logger.warning(f"No data found for current month {current_month}/{current_year}")

            # Commit the transaction
            self.env.cr.commit()
            _logger.info("Revenue data update process completed successfully")

        except Exception as e:
            # Rollback on error
            self.env.cr.rollback()
            _logger.error(f"Error in update_revenue_data: {str(e)}")
            raise

    @api.model
    def manual_update_revenue_data(self):
        """
        Method untuk manual update (bisa dipanggil dari UI)
        """
        return self.update_revenue_data()

    # Method untuk mendapatkan summary data
    @api.model
    def get_revenue_summary(self, year=None, month=None):
        """
        Get summary data berdasarkan tahun dan bulan
        """
        domain = []
        if year:
            domain.append(('year_of_order', '=', year))
        if month:
            domain.append(('month_of_order', '=', month))

        records = self.search(domain)

        if not records:
            return {
                'total_revenue': 0,
                'total_bop': 0,
                'avg_bop_percentage': 0,
                'customer_count': 0
            }

        total_revenue = sum(records.mapped('actual_revenue'))
        total_bop = sum(records.mapped('total_bop'))
        avg_bop_percentage = sum(records.mapped('bop_to_rev_percentage')) / len(records) if records else 0
        customer_count = len(records.mapped('customer_name'))

        return {
            'total_revenue': total_revenue,
            'total_bop': total_bop,
            'avg_bop_percentage': round(avg_bop_percentage, 2),
            'customer_count': customer_count
        }