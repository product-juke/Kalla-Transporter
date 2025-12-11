# -*- coding: utf-8 -*-
from email.policy import default

from odoo import models, fields, api
from datetime import datetime, date
from calendar import monthrange
import logging

_logger = logging.getLogger(__name__)


class MartCustomerVehicleUtilizationSmry(models.Model):
    _name = 'mart.customer.vehicle.utilization.smry'
    _description = 'Mart Utilization By Vehicle and Customer'

    # Fields berdasarkan query SELECT yang baru
    do_id = fields.Integer(string='DO ID', required=True)
    do_create_date = fields.Datetime(string='DO Create Date')
    year = fields.Integer(string='Year', required=True)
    month = fields.Integer(string='Month', required=True)
    month_name = fields.Char(string='Month Name', required=True)
    day_of_order = fields.Integer(string='Day of Order', required=True)
    customer_id = fields.Integer(string='Customer ID')
    customer_name = fields.Char(string='Customer Name')
    vehicle_name = fields.Char(string='Vehicle Name', required=True)
    project = fields.Char(string='PROJECT', required=True)
    license_plate = fields.Char(string='License Plate', required=True)
    category_name = fields.Char(string='Category Name', required=True)
    total = fields.Float(string='TOTAL', default=0.0)
    status = fields.Char(string='Status', required=True)
    order_date = fields.Date(string='Order Date', required=True)

    # Additional fields untuk tracking
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now)
    updated_date = fields.Datetime(string='Updated Date', default=fields.Datetime.now)

    @api.model
    def refresh_mart_data(self):
        """
        Method untuk refresh data mart vehicle utilization
        - Jika data kosong: insert semua data dari query
        - Jika ada data: hapus data bulan/tahun ini, insert data baru bulan/tahun ini
        """
        try:
            _logger.info("Starting Mart Customer Vehicle Utilization refresh process...")

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

            _logger.info("Mart Customer Vehicle Utilization refresh process completed successfully.")

        except Exception as e:
            _logger.error(f"Error in refresh_mart_data: {str(e)}")
            raise

    def _insert_all_data_from_query(self):
        """Insert semua data dari query ke dalam model"""
        query = """
        SELECT 
            fd.id as do_id,
            EXTRACT(YEAR FROM fd.date) AS year,
            EXTRACT(MONTH FROM fd.date) AS month,
            TO_CHAR(fd.date, 'TMMonth') AS month_name,
            EXTRACT(DAY FROM fd.date) AS day_of_order,
            rp.id as customer_id,
            rp.name as customer_name,
            fv.name as vehicle_name,
            (CASE WHEN fv.customer_id is null THEN 'All Project' ELSE 'Dedicated' end) as project,
            fv.license_plate as license_plate,
            fvmc.name as category_name,
            (CASE WHEN sol.is_header = TRUE THEN sol.sla ELSE 0 end) as total,
            (CASE WHEN fd.id is not null THEN 'UTILIZATION' end) as status,
            fd.date as order_date,
            fd.create_date as do_create_date
        FROM 
            fleet_do fd
        JOIN 
            do_po_line_rel dplr ON fd.id = dplr.do_id
        JOIN 
            sale_order_line sol ON sol.id = dplr.po_line_id
        JOIN 
            sale_order so ON so.id = sol.order_id
        JOIN 
            fleet_vehicle fv ON fv.id = fd.vehicle_id
        JOIN 
            res_partner rp ON rp.id = so.partner_id
        JOIN 
            fleet_vehicle_model_category fvmc on fvmc.id = fv.category_id
        WHERE 
            fd.date is not null
        GROUP BY 
            fd.date, fv.name, fv.license_plate, fvmc.name, rp.id, rp.name, 
            fv.customer_id, fd.id, sol.sla, sol.is_header
        ORDER BY 
            fd.date desc
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure order_date is not None
            if row[13] is None:
                _logger.warning(f"Skipping row with null order_date: {row}")
                continue

            year = int(row[1]) if row[1] else ''
            month = int(row[2]) if row[2] else ''

            # Mendapatkan awal bulan
            start_date = date(year, month, 1)

            # Mendapatkan akhir bulan menggunakan monthrange
            last_day = monthrange(year, month)[1]  # monthrange returns (weekday, days_in_month)
            end_date = date(year, month, last_day)

            staging_datas = self.env['mart.vehicle.utilization'].search([
                ('date', '>=', start_date),  # Awal bulan
                ('date', '<=', end_date),  # Akhir bulan
                ('category', '=', row[10]),  # Filter berdasarkan customer ID
                ('vehicle_name', '=', row[7]),  # Filter berdasarkan vehicle name
                ('license_plate', '=', row[9]),
            ])

            ready_for_use_datas = staging_datas.filtered(lambda x: x.status == 'READY FOR USE')
            breakdown_datas = staging_datas.filtered(lambda x: x.status == 'BREAKDOWN')
            driver_not_ready_datas = staging_datas.filtered(lambda x: x.status == 'DRIVER NOT READY')

            mart_data.append({
                'do_id': int(row[0]) if row[0] else 0,
                'year': int(year) if year else 0,
                'month': int(month) if month else 0,
                'month_name': row[3] or '',
                'day_of_order': int(row[4]) if row[4] else 0,
                'customer_id': int(row[5]) if row[5] else 0,
                'customer_name': row[6] or '',
                'vehicle_name': row[7] or '',
                'project': row[8] or '',
                'license_plate': row[9] or '',
                'category_name': row[10] or '',
                'total': float(row[11]) if row[11] else 0.0,
                'status': row[12] or '',
                'order_date': row[13],  # Now guaranteed to be not None
                'do_create_date': row[14],
            })

            # READY FOR USE
            for rfu in ready_for_use_datas:
                print('rfu', rfu)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'READY FOR USE',
                    'order_date': rfu.date,  # Now guaranteed to be not None
                    'do_create_date': None,
                })

            # BREAKDOWN
            for bd in breakdown_datas:
                print('bd', bd)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'BREAKDOWN',
                    'order_date': bd.date,  # Now guaranteed to be not None
                    'do_create_date': None,
                })

            # BREAKDOWN
            for dnr in driver_not_ready_datas:
                print('dnr', dnr)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'DRIVER NOT READY',
                    'order_date': dnr.date,  # Now guaranteed to be not None
                    'do_create_date': None,
                })

        # Batch create untuk performa yang lebih baik
        if mart_data:
            self.create(mart_data)
            _logger.info(f"Inserted {len(mart_data)} records into mart.customer.vehicle.utilization.smry")

    def _refresh_current_month_data(self, year, month):
        """Hapus data bulan/tahun ini dan insert yang baru"""
        # Hapus data untuk bulan dan tahun ini
        records_to_delete = self.search([
            ('year', '=', year),
            ('month', '=', month)
        ])

        if records_to_delete:
            records_to_delete.unlink()
            _logger.info(f"Deleted {len(records_to_delete)} records for {month}/{year}")

        # Insert data baru untuk bulan dan tahun ini
        query = """
        SELECT 
            fd.id as do_id,
            EXTRACT(YEAR FROM fd.date) AS year,
            EXTRACT(MONTH FROM fd.date) AS month,
            TO_CHAR(fd.date, 'TMMonth') AS month_name,
            EXTRACT(DAY FROM fd.date) AS day_of_order,
            rp.id as customer_id,
            rp.name as customer_name,
            fv.name as vehicle_name,
            (CASE WHEN fv.customer_id is null THEN 'All Project' ELSE 'Dedicated' end) as project,
            fv.license_plate as license_plate,
            fvmc.name as category_name,
            (CASE WHEN sol.is_header = TRUE THEN sol.sla ELSE 0 end) as total,
            (CASE WHEN fd.id is not null THEN 'UTILIZATION' end) as status,
            fd.date as order_date,
            fd.create_date as do_create_date
        FROM 
            fleet_do fd
        JOIN 
            do_po_line_rel dplr ON fd.id = dplr.do_id
        JOIN 
            sale_order_line sol ON sol.id = dplr.po_line_id
        JOIN 
            sale_order so ON so.id = sol.order_id
        JOIN 
            fleet_vehicle fv ON fv.id = fd.vehicle_id
        JOIN 
            res_partner rp ON rp.id = so.partner_id
        JOIN 
            fleet_vehicle_model_category fvmc on fvmc.id = fv.category_id
        WHERE 
            EXTRACT(YEAR FROM fd.date) = %s
            AND EXTRACT(MONTH FROM fd.date) = %s
            AND fd.date is not null
        GROUP BY 
            fd.date, fv.name, fv.license_plate, fvmc.name, rp.id, rp.name, 
            fv.customer_id, fd.id, sol.sla, sol.is_header
        ORDER BY 
            fd.date desc
        """

        self.env.cr.execute(query, (year, month))
        results = self.env.cr.fetchall()

        # Convert hasil query ke format yang sesuai untuk create
        mart_data = []
        for row in results:
            # Additional validation to ensure order_date is not None
            if row[13] is None:
                _logger.warning(f"Skipping row with null order_date: {row}")
                continue

            year = int(row[1]) if row[1] else ''
            month = int(row[2]) if row[2] else ''

            # Mendapatkan awal bulan
            start_date = date(year, month, 1)

            # Mendapatkan akhir bulan menggunakan monthrange
            last_day = monthrange(year, month)[1]  # monthrange returns (weekday, days_in_month)
            end_date = date(year, month, last_day)

            staging_datas = self.env['mart.vehicle.utilization'].search([
                ('date', '>=', start_date),  # Awal bulan
                ('date', '<=', end_date),  # Akhir bulan
                ('category', '=', row[10]),  # Filter berdasarkan customer ID
                ('vehicle_name', '=', row[7]),  # Filter berdasarkan vehicle name
                ('license_plate', '=', row[9]),
            ])

            ready_for_use_datas = staging_datas.filtered(lambda x: x.status == 'READY FOR USE')
            breakdown_datas = staging_datas.filtered(lambda x: x.status == 'BREAKDOWN')
            driver_not_ready_datas = staging_datas.filtered(lambda x: x.status == 'DRIVER NOT READY')

            mart_data.append({
                'do_id': int(row[0]) if row[0] else 0,
                'year': int(year) if year else 0,
                'month': int(month) if month else 0,
                'month_name': row[3] or '',
                'day_of_order': int(row[4]) if row[4] else 0,
                'customer_id': int(row[5]) if row[5] else 0,
                'customer_name': row[6] or '',
                'vehicle_name': row[7] or '',
                'project': row[8] or '',
                'license_plate': row[9] or '',
                'category_name': row[10] or '',
                'total': float(row[11]) if row[11] else 0.0,
                'status': row[12] or '',
                'order_date': row[13],  # Now guaranteed to be not None
                'do_create_date': row[14],
            })

            # READY FOR USE
            for rfu in ready_for_use_datas:
                print('rfu', rfu)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'READY FOR USE',
                    'order_date': rfu.date,  # Now guaranteed to be not None
                    'do_create_date': None,
                })

            # BREAKDOWN
            for bd in breakdown_datas:
                print('bd', bd)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'BREAKDOWN',
                    'order_date': bd.date,  # Now guaranteed to be not None
                    'do_create_date': None,
                })

            # BREAKDOWN
            for dnr in driver_not_ready_datas:
                print('dnr', dnr)
                mart_data.append({
                    'do_id': None,
                    'year': int(year) if year else 0,
                    'month': int(month) if month else 0,
                    'month_name': row[3] or '',
                    'day_of_order': None,
                    'customer_id': int(row[5]) if row[5] else 0,
                    'customer_name': row[6] or '',
                    'vehicle_name': row[7] or '',
                    'project': row[8] or '',
                    'license_plate': row[9] or '',
                    'category_name': row[10] or '',
                    'total': 1,
                    'status': 'DRIVER NOT READY',
                    'order_date': dnr.date,  # Now guaranteed to be not None
                    'do_create_date': None,
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
        return super(MartCustomerVehicleUtilizationSmry, self).write(vals)