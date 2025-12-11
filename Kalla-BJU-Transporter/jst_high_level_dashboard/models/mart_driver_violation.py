# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date
import calendar
import logging

_logger = logging.getLogger(__name__)


class MartDriverViolation(models.Model):
    _name = 'mart.driver.violation'
    _description = 'Data Mart Driver Violation'
    _order = 'nama_driver, tanggal_pelanggaran asc'

    nama_driver = fields.Char(string='Nama Driver', required=True, index=True)
    tanggal_pelanggaran = fields.Date(string='Tanggal Pelanggaran', required=True, index=True)
    jenis_pelanggaran = fields.Char(string='Jenis Pelanggaran', required=True)
    deskripsi_pelanggaran = fields.Text(string='Deskripsi Pelanggaran')
    action_plan = fields.Text(string='Action Plan')

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart dari query disciplinary line

        Args:
            bulan_ini_only (bool): Jika True, hanya generate data bulan ini
        """
        try:
            # Jika bulan_ini_only=True, hapus data bulan berjalan
            if bulan_ini_only:
                current_month_start = date.today().replace(day=1)
                last_day_of_month = calendar.monthrange(
                    current_month_start.year,
                    current_month_start.month
                )[1]
                current_month_end = current_month_start.replace(day=last_day_of_month)

                # Hapus data bulan ini
                existing_records = self.search([
                    ('tanggal_pelanggaran', '>=', current_month_start),
                    ('tanggal_pelanggaran', '<=', current_month_end)
                ])
                if existing_records:
                    existing_records.unlink()
                    _logger.info(f"Deleted {len(existing_records)} records for current month")

            # Query untuk mengambil data dari disciplinary line
            query = """
                SELECT 
                    he.name AS nama_driver,
                    dl.date AS tanggal_pelanggaran,
                    dl.type_violation AS jenis_pelanggaran,
                    hv.violation AS deskripsi_pelanggaran,
                    dl.action_plan
                FROM disicplinary_line dl
                JOIN hr_employee he ON he.id = dl.employee_id
                JOIN hr_violation hv ON hv.id = dl.violation_id
                WHERE dl.date IS NOT NULL
            """

            # Jika hanya bulan ini, tambahkan filter tanggal
            if bulan_ini_only:
                current_month_start = date.today().replace(day=1)
                last_day_of_month = calendar.monthrange(
                    current_month_start.year,
                    current_month_start.month
                )[1]
                current_month_end = current_month_start.replace(day=last_day_of_month)

                query += f"""
                    AND dl.date >= '{current_month_start}'
                    AND dl.date <= '{current_month_end}'
                """

            query += " ORDER BY he.name, dl.date ASC"

            # Execute query
            self.env.cr.execute(query)
            results = self.env.cr.fetchall()

            if not results:
                _logger.info("No data found to insert into data mart")
                return

            # Prepare data untuk bulk create
            data_to_create = []
            for row in results:
                data_to_create.append({
                    'nama_driver': row[0] or '',
                    'tanggal_pelanggaran': row[1],
                    'jenis_pelanggaran': row[2] or '',
                    'deskripsi_pelanggaran': row[3] or '',
                    'action_plan': row[4] or '',
                })

            # Bulk create untuk performance yang lebih baik
            if data_to_create:
                self.create(data_to_create)
                _logger.info(f"Successfully inserted {len(data_to_create)} records into mart_driver_violation")

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            raise

    @api.model
    def cron_generate_data_mart(self):
        """
        Cron job untuk generate data mart
        - Jika tabel kosong: generate semua data
        - Jika tabel ada: hapus dan generate ulang data bulan ini
        """
        try:
            _logger.info("Starting cron job for data mart generation")

            # Cek apakah tabel kosong
            record_count = self.search_count([])

            if record_count == 0:
                # Tabel kosong, generate semua data
                _logger.info("Table is empty, generating all data")
                self.generate_data_mart(bulan_ini_only=False)
            else:
                # Tabel sudah ada, generate ulang data bulan ini
                _logger.info("Table has data, regenerating current month data")
                self.generate_data_mart(bulan_ini_only=True)

            _logger.info("Cron job completed successfully")

        except Exception as e:
            _logger.error(f"Error in cron job: {str(e)}")
            raise

    @api.model
    def manual_refresh_all_data(self):
        """
        Method untuk refresh manual semua data
        Menghapus semua data existing dan generate ulang
        """
        try:
            _logger.info("Starting manual refresh of all data")

            # Hapus semua data existing
            existing_records = self.search([])
            if existing_records:
                existing_records.unlink()
                _logger.info(f"Deleted {len(existing_records)} existing records")

            # Generate ulang semua data
            self.generate_data_mart(bulan_ini_only=False)

            _logger.info("Manual refresh completed successfully")

        except Exception as e:
            _logger.error(f"Error in manual refresh: {str(e)}")
            raise

    def name_get(self):
        """Override name_get untuk display name yang lebih informatif"""
        result = []
        for record in self:
            name = f"{record.nama_driver} - {record.tanggal_pelanggaran} - {record.jenis_pelanggaran}"
            result.append((record.id, name))
        return result