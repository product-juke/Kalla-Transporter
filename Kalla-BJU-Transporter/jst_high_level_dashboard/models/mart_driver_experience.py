# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class MartDriverExperience(models.Model):
    _name = 'mart.driver.experience'
    _description = 'Driver Experience Data Mart'
    _order = 'driver_name asc, total_mileage desc'

    # Fields berdasarkan query SQL
    driver_name = fields.Char('Driver Name', required=True, index=True)
    vehicle_name = fields.Char('Vehicle Name', required=True)
    no_lambung = fields.Char('No Lambung')
    no_plat = fields.Char('License Plate')
    category = fields.Char('Vehicle Category')
    product = fields.Char('Product Category')
    customer = fields.Char('Customer')
    total_mileage = fields.Float('Total Mileage', digits=(12, 2))
    total_driving_hours = fields.Float('Total Driving Hours', digits=(12, 2))
    last_record_date = fields.Datetime('Last Record Date')
    last_activity_date = fields.Date('Last Activity Date')
    total_delivery_orders = fields.Integer('Total Delivery Orders')

    # Fields baru untuk employee resume information
    partner_id = fields.Many2one('res.partner', 'Partner', index=True)
    latest_resume_type = fields.Char('Latest Resume Type')

    # Fields tambahan untuk tracking
    created_month = fields.Char('Created Month', compute='_compute_created_month', store=True)

    @api.depends('last_record_date')
    def _compute_created_month(self):
        """Compute created month from last_record_date untuk keperluan filtering"""
        for record in self:
            if record.last_record_date:
                record.created_month = record.last_record_date.strftime('%Y-%m')
            else:
                record.created_month = False

    def _get_base_query(self):
        """Return base SQL query"""
        return """
            SELECT 
                rpd.name AS driver_name,
                fv.name AS vehicle_name,
                fv.no_lambung AS no_lambung,
                fv.license_plate AS no_plat,
                fvmc.name AS category,
                pc.name AS product,
                rp.name AS customer,
                COALESCE(SUM(sol.distance), 0) AS total_mileage,
                COALESCE(SUM(sol.sla), 0) * 24 AS total_driving_hours,
                MAX(sol.create_date) AS last_record_date,
                MAX(DATE(sol.create_date)) AS last_activity_date,
                COUNT(DISTINCT sol.do_id) AS total_delivery_orders,
                emp_resume.partner_id,
                hrl_type.name AS latest_resume_type
            FROM sale_order_line sol
            INNER JOIN (
                SELECT 
                    do_id, 
                    MAX(bop) AS max_bop
                FROM sale_order_line
                WHERE do_id IS NOT NULL
                GROUP BY do_id
            ) max_vals ON sol.do_id = max_vals.do_id AND sol.bop = max_vals.max_bop
            INNER JOIN fleet_do fd ON fd.id = sol.do_id
            INNER JOIN fleet_vehicle fv ON fv.id = fd.vehicle_id
            INNER JOIN res_partner rpd ON rpd.id = fv.driver_id
            INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id
            INNER JOIN product_category pc ON pc.id = fv.product_category_id
            INNER JOIN res_partner rp ON rp.id = sol.order_partner_id
            -- Join with employee resume data
            LEFT JOIN (
                SELECT 
                    he.partner_id,
                    a.line_type_id,
                    ROW_NUMBER() OVER (PARTITION BY a.employee_id ORDER BY a.create_date DESC) AS num
                FROM hr_resume_line a
                JOIN hr_employee he ON he.id = a.employee_id
            ) emp_resume ON emp_resume.num = 1 AND emp_resume.partner_id = rpd.id
            LEFT JOIN hr_resume_line_type hrl_type ON hrl_type.id = emp_resume.line_type_id
            {where_clause}
            GROUP BY 
                rpd.name, 
                fv.name, 
                fv.no_lambung, 
                fv.license_plate, 
                fvmc.name, 
                pc.name, 
                rp.name, 
                emp_resume.partner_id, 
                hrl_type.name
            ORDER BY rpd.name ASC, total_mileage DESC
        """

    def _execute_query_and_create_records(self, where_clause=""):
        """Execute query dan create records"""
        query = self._get_base_query().format(where_clause=where_clause)

        _logger.info("Executing query: %s", query)

        try:
            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            _logger.info("Query returned %d records", len(results))

            # Batch create untuk performance yang lebih baik
            records_to_create = []
            for row in results:
                records_to_create.append({
                    'driver_name': row['driver_name'] or '',
                    'vehicle_name': row['vehicle_name'] or '',
                    'no_lambung': row['no_lambung'] or '',
                    'no_plat': row['no_plat'] or '',
                    'category': row['category'] or '',
                    'product': row['product'] or '',
                    'customer': row['customer'] or '',
                    'total_mileage': row['total_mileage'] or 0.0,
                    'total_driving_hours': row['total_driving_hours'] or 0.0,
                    'last_record_date': row['last_record_date'],
                    'last_activity_date': row['last_activity_date'],
                    'total_delivery_orders': row['total_delivery_orders'] or 0,
                    'partner_id': row['partner_id'] or False,
                    'latest_resume_type': row['latest_resume_type'] or '',
                })

            if records_to_create:
                self.create(records_to_create)
                _logger.info("Created %d mart records", len(records_to_create))

            return len(records_to_create)

        except Exception as e:
            _logger.error("Error executing data mart query: %s", str(e))
            raise

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart records

        Args:
            bulan_ini_only (bool): Jika True, hapus data bulan ini dan generate ulang
                                 Jika False, generate semua data (biasanya untuk tabel kosong)
        """
        _logger.info("Starting data mart generation. bulan_ini_only: %s", bulan_ini_only)

        current_month = date.today().strftime('%Y-%m')

        if bulan_ini_only:
            # Hapus data bulan ini
            current_month_records = self.search([('created_month', '=', current_month)])
            if current_month_records:
                current_month_records.unlink()
                _logger.info("Deleted %d records for current month: %s", len(current_month_records), current_month)

            # Generate data untuk bulan ini saja
            where_clause = f"WHERE DATE(sol.create_date) >= '{date.today().replace(day=1)}'"
            created_count = self._execute_query_and_create_records(where_clause)

        else:
            # Generate semua data (untuk tabel kosong)
            created_count = self._execute_query_and_create_records()

        _logger.info("Data mart generation completed. Created %d records", created_count)
        return created_count

    @api.model
    def _cron_update_data_mart(self):
        """
        Cron job untuk update data mart harian
        - Jika tabel kosong: generate semua data
        - Jika tabel ada isi: hapus data bulan ini dan generate ulang
        """
        _logger.info("Starting scheduled data mart update")

        try:
            record_count = self.search_count([])

            if record_count == 0:
                # Tabel kosong, generate semua data
                _logger.info("Table is empty, generating all data")
                self.generate_data_mart(bulan_ini_only=False)
            else:
                # Tabel ada isi, update data bulan ini
                _logger.info("Table has data, updating current month only")
                self.generate_data_mart(bulan_ini_only=True)

        except Exception as e:
            _logger.error("Error in scheduled data mart update: %s", str(e))
            raise

    @api.model
    def manual_full_regenerate(self):
        """Manual method untuk regenerate semua data (hapus semua lalu generate ulang)"""
        _logger.info("Starting manual full regeneration")

        # Hapus semua data
        all_records = self.search([])
        if all_records:
            all_records.unlink()
            _logger.info("Deleted all %d existing records", len(all_records))

        # Generate ulang semua data
        created_count = self.generate_data_mart(bulan_ini_only=False)

        _logger.info("Manual full regeneration completed. Created %d records", created_count)
        return created_count