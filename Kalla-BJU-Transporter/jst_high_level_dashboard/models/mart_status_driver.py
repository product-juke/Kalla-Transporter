from odoo import models, fields, api
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class MartStatusDriver(models.Model):
    _name = 'mart.status.driver'
    _description = 'Data Mart Status Driver'
    _order = 'driver_name asc'

    # Fields berdasarkan hasil query
    employee_id = fields.Integer(string='Employee ID')
    driver_id = fields.Integer(string='Driver ID', required=True)
    driver_name = fields.Char(string='Driver Name', required=True)
    availability_status = fields.Char(string='Availability Status')
    license_status = fields.Integer(string='License Status')
    competence_status_name = fields.Char(string='Competence Status Name')
    competence_status = fields.Integer(string='Competence Status')
    vehicle_id = fields.Integer(string='Vehicle ID')
    license_plate = fields.Char(string='License Plate')
    vehicle_status = fields.Char(string='Vehicle Status')
    delivery_status = fields.Char(string='Delivery Status')

    # Field tambahan untuk tracking
    created_date = fields.Date(string='Created Date', default=fields.Date.today)
    created_datetime = fields.Datetime(string='Created Datetime', default=fields.Datetime.now)

    def _get_driver_status_query(self):
        """Return the SQL query for driver status data mart"""
        return """
            SELECT 
                he.id AS employee_id,
                rp.id AS driver_id,
                rp.name AS driver_name,
                (CASE 
                    WHEN UPPER(rp.availability) = 'READY' THEN 'Ready' 
                    ELSE 'Not Ready' 
                END) AS availability_status,
                (CASE 
                    WHEN rp.is_license_expiring IS TRUE THEN 1 
                    ELSE 0 
                END) AS license_status,
                latest_resume.type AS competence_status_name,
                (CASE 
                    WHEN UPPER(latest_resume.type) = 'TRAINING' THEN 1 
                    ELSE 0 
                END) AS competence_status,
                single_vehicle.vehicle_id,
                single_vehicle.license_plate,
                single_vehicle.vehicle_status,
                (CASE 
                    WHEN single_vehicle.delivery_status IS NULL THEN 'STANDBY' 
                    ELSE single_vehicle.delivery_status 
                END) AS delivery_status
            FROM res_partner rp
            LEFT JOIN hr_employee he ON he.work_contact_id = rp.id
            LEFT JOIN (
                SELECT 
                    hrl.employee_id,
                    hrlt.name AS type,
                    hrl.date_end,
                    hrl.date_start,
                    hrl.id,
                    ROW_NUMBER() OVER (
                        PARTITION BY hrl.employee_id 
                        ORDER BY hrl.date_end DESC NULLS LAST, 
                                hrl.date_start DESC NULLS LAST, 
                                hrl.id DESC
                    ) AS rn
                FROM hr_resume_line hrl
                LEFT JOIN hr_resume_line_type hrlt ON hrlt.id = hrl.line_type_id
            ) latest_resume ON he.id = latest_resume.employee_id AND latest_resume.rn = 1
            LEFT JOIN (
                SELECT 
                    fv.driver_id,
                    fv.id AS vehicle_id,
                    fv.license_plate,
                    fv.vehicle_status,
                    (CASE 
                        WHEN fv.vehicle_status = 'on_going' THEN 'ON DELIVERY'
                        WHEN fv.vehicle_status = 'on_return' THEN 'ON RETURN'
                        ELSE 'STANDBY'
                    END) AS delivery_status,
                    ROW_NUMBER() OVER (
                        PARTITION BY fv.driver_id 
                        ORDER BY CASE 
                            WHEN fv.vehicle_status = 'on_going' THEN 1
                            WHEN fv.vehicle_status = 'on_return' THEN 2
                            ELSE 3
                        END,
                        fv.id ASC
                    ) AS vehicle_rn
                FROM fleet_vehicle fv
                WHERE fv.driver_id IS NOT NULL
            ) single_vehicle ON rp.id = single_vehicle.driver_id AND single_vehicle.vehicle_rn = 1
            WHERE rp.is_driver IS TRUE
            ORDER BY rp.name ASC
        """

    @api.model
    def generate_data_mart(self, hari_ini_only=False):
        """
        Generate data mart for driver status

        Args:
            hari_ini_only (bool): If True, only generate today's data after clearing it
        """
        try:
            today = fields.Date.today()

            # Jika hari_ini_only=True, hapus data hari ini
            if hari_ini_only:
                _logger.info("Menghapus data mart driver status untuk tanggal: %s", today)
                self.search([('created_date', '=', today)]).unlink()
            else:
                # Jika tabel kosong, generate semua data
                existing_count = self.search_count([])
                if existing_count > 0:
                    _logger.info("Tabel sudah berisi data (%s records), menggunakan mode hari_ini_only", existing_count)
                    return self.generate_data_mart(hari_ini_only=True)

                _logger.info("Tabel kosong, generating semua data mart driver status")

            # Execute query untuk mendapatkan data
            query = self._get_driver_status_query()
            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            # Prepare data untuk bulk create
            data_to_create = []
            for result in results:
                data_to_create.append({
                    'employee_id': result.get('employee_id'),
                    'driver_id': result['driver_id'],
                    'driver_name': result['driver_name'],
                    'availability_status': result.get('availability_status'),
                    'license_status': result.get('license_status', 0),
                    'competence_status_name': result.get('competence_status_name'),
                    'competence_status': result.get('competence_status', 0),
                    'vehicle_id': result.get('vehicle_id'),
                    'license_plate': result.get('license_plate'),
                    'vehicle_status': result.get('vehicle_status'),
                    'delivery_status': result.get('delivery_status', 'STANDBY'),
                    'created_date': today,
                    'created_datetime': fields.Datetime.now(),
                })

            # Bulk create records
            if data_to_create:
                self.create(data_to_create)
                _logger.info("Berhasil generate %s records data mart driver status", len(data_to_create))
            else:
                _logger.warning("Tidak ada data driver yang ditemukan")

        except Exception as e:
            _logger.error("Error saat generate data mart driver status: %s", str(e))
            raise

    @api.model
    def cron_generate_data_mart(self):
        """
        Cron job method untuk generate data mart setiap jam
        - Jika tabel kosong: generate semua data
        - Jika tabel ada: hapus data hari ini dan generate ulang data hari ini
        """
        try:
            _logger.info("Starting cron job: Generate Data Mart Driver Status")

            existing_count = self.search_count([])

            if existing_count == 0:
                # Tabel kosong, generate semua data
                _logger.info("Tabel kosong, generate semua data")
                self.generate_data_mart(hari_ini_only=False)
            else:
                # Tabel sudah ada, refresh data hari ini
                _logger.info("Tabel sudah berisi %s records, refresh data hari ini", existing_count)
                self.generate_data_mart(hari_ini_only=True)

            _logger.info("Cron job completed successfully")

        except Exception as e:
            _logger.error("Error dalam cron job generate data mart driver status: %s", str(e))

    def name_get(self):
        """Override name_get to show driver name"""
        result = []
        for record in self:
            name = f"{record.driver_name} - {record.availability_status}"
            result.append((record.id, name))
        return result