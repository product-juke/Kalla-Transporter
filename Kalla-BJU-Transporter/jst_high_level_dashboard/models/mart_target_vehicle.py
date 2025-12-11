# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MartTargetVehicle(models.Model):
    _name = 'mart.target.vehicle'
    _description = 'Vehicle Target Data Mart'
    _order = 'category_name asc, year desc, month asc, vehicle_name asc'
    _rec_name = 'vehicle_name_complete'

    # Vehicle identification fields
    vehicle_id = fields.Integer(
        string='Vehicle ID',
        required=True,
        help="Reference to fleet.vehicle ID"
    )
    vehicle_name = fields.Char(
        string='Vehicle Name',
        required=True,
        help="Short vehicle name"
    )
    vehicle_name_complete = fields.Char(
        string='Complete Vehicle Name',
        required=True,
        help="Complete vehicle name"
    )
    no_lambung = fields.Char(
        string='No Lambung',
        help="Vehicle hull number"
    )
    license_plate = fields.Char(
        string='License Plate',
        help="Vehicle license plate"
    )
    category_name = fields.Char(
        string='Category Name',
        required=True,
        help="Vehicle category name"
    )

    # Time dimension fields
    year = fields.Integer(
        string='Year',
        required=True,
        help="Target year"
    )
    month = fields.Integer(
        string='Month',
        required=True,
        help="Target month (1-12)"
    )
    date = fields.Date(
        string='Date',
        required=True,
        help="Date representation of year-month"
    )

    # Financial metrics
    actual_revenue = fields.Float(
        string='Actual Revenue',
        digits=(16, 2),
        help="Sum of actual revenue from sales"
    )
    target_revenue = fields.Float(
        string='Target Revenue',
        digits=(16, 2),
        help="Sum of target revenue"
    )
    achievement = fields.Float(
        string='Achievement',
        digits=(16, 2),
        help="Achievement percentage (actual/target)"
    )

    # Utilization metrics
    actual_utilization_days = fields.Integer(
        string='Actual Utilization Days',
        help="Sum of actual utilization days"
    )
    target_utilization_days = fields.Integer(
        string='Target Utilization Days',
        help="Sum of target utilization days"
    )
    actual_utilization_days_label = fields.Char(
        string='Actual Utilization Label',
        help="Formatted actual utilization days with 'Hari' suffix"
    )
    target_utilization_days_label = fields.Char(
        string='Target Utilization Label',
        help="Formatted target utilization days with 'Hari' suffix"
    )

    # Performance indicators
    potential_to_target = fields.Char(
        string='Potential to Target',
        help="Status potential without icon"
    )
    potential_to_target_with_icon = fields.Char(
        string='Potential to Target (with Icon)',
        help="Status potential with icon"
    )

    _sql_constraints = [
        ('unique_vehicle_year_month',
         'UNIQUE(vehicle_id, year, month)',
         'Vehicle, year, and month combination must be unique!')
    ]

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart dari query SQL

        Args:
            bulan_ini_only (bool): Jika True, hanya generate data bulan ini
        """
        try:
            current_date = datetime.now()
            current_year = current_date.year
            current_month = current_date.month

            if bulan_ini_only:
                # Hapus data bulan ini saja
                existing_records = self.search([
                    ('year', '=', current_year),
                    ('month', '=', current_month)
                ])
                if existing_records:
                    existing_records.unlink()
                    _logger.info(
                        f"Deleted {len(existing_records)} records for current month ({current_year}-{current_month})")

                # Generate query dengan filter bulan ini
                where_condition = f"""
                WHERE vtl.year = {current_year} 
                AND vtl.month = {current_month}
                """
            else:
                # Cek apakah tabel kosong
                record_count = self.search_count([])
                if record_count == 0:
                    where_condition = ""  # Generate semua data
                    _logger.info("Table is empty, generating all data")
                else:
                    # Jika tabel tidak kosong tapi tidak bulan_ini_only,
                    # tetap generate ulang data bulan ini
                    existing_records = self.search([
                        ('year', '=', current_year),
                        ('month', '=', current_month)
                    ])
                    if existing_records:
                        existing_records.unlink()
                        _logger.info(f"Deleted {len(existing_records)} records for current month")

                    where_condition = f"""
                    WHERE vtl.year = {current_year} 
                    AND vtl.month = {current_month}
                    """

            # Query SQL utama - sesuai dengan query yang diberikan
            sql_query = f"""
                SELECT
                    fv.id AS vehicle_id,
                    fv.vehicle_name,
                    fv.name AS vehicle_name_complete,
                    fv.no_lambung,
                    fv.license_plate,
                    fvmc.name AS category_name,
                    vtl.year,
                    vtl.month,
                    make_date(vtl.year, vtl.month, 1) AS date,
                    SUM(sol.price_unit) AS actual_revenue,
                    SUM(vtl.total_target) AS target_revenue,
                    ROUND(
                        CASE 
                            WHEN SUM(vtl.total_target) <= 0 THEN 0
                            ELSE SUM(sol.price_unit) / SUM(vtl.total_target)
                        END,
                    2) AS achievement,
                    SUM(sol.sla) AS actual_utilization_days,
                    SUM(vtl.target_days_utilization) AS target_utilization_days,
                    CONCAT(SUM(sol.sla), ' Hari') AS actual_utilization_days_label,
                    CONCAT(SUM(vtl.target_days_utilization), ' Hari') AS target_utilization_days_label,
                    CASE 
                        WHEN (SUM(sol.price_unit) / SUM(sol.sla) * SUM(vtl.target_days_utilization)) < SUM(vtl.total_target) 
                        THEN 'At Risk️'
                        ELSE 'Exceeding Target'
                    END AS potential_to_target,
                    CASE 
                        WHEN (SUM(sol.price_unit) / SUM(sol.sla) * SUM(vtl.target_days_utilization)) < SUM(vtl.total_target) 
                        THEN 'At Risk ‼️'
                        ELSE 'Exceeding Target ✔️'
                    END AS potential_to_target_with_icon
                FROM
                    fleet_vehicle fv
                INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id
                INNER JOIN fleet_do fd ON fd.vehicle_id = fv.id
                INNER JOIN sale_order_line sol ON sol.do_id = fd.id
                INNER JOIN vehicle_target_line vtl ON vtl.vehicle_id = fv.id
                {where_condition}
                GROUP BY
                    fv.id,
                    fvmc.name,
                    vtl.year,
                    vtl.month
                ORDER BY
                    fvmc.name ASC,
                    vtl.year DESC,
                    vtl.month ASC
            """

            # Eksekusi query
            self.env.cr.execute(sql_query)
            results = self.env.cr.dictfetchall()

            # Insert data baru
            records_created = 0
            for result in results:
                # Validasi data sebelum create
                if (result.get('vehicle_id') and result.get('category_name') and
                        result.get('year') and result.get('month')):
                    try:
                        self.create({
                            'vehicle_id': result['vehicle_id'],
                            'vehicle_name': result['vehicle_name'] or '',
                            'vehicle_name_complete': result['vehicle_name_complete'] or '',
                            'no_lambung': result['no_lambung'] or '',
                            'license_plate': result['license_plate'] or '',
                            'category_name': result['category_name'],
                            'year': result['year'],
                            'month': result['month'],
                            'date': result['date'],
                            'actual_revenue': result['actual_revenue'] or 0.0,
                            'target_revenue': result['target_revenue'] or 0.0,
                            'achievement': result['achievement'] or 0.0,
                            'actual_utilization_days': result['actual_utilization_days'] or 0,
                            'target_utilization_days': result['target_utilization_days'] or 0,
                            'actual_utilization_days_label': result['actual_utilization_days_label'] or '0 Hari',
                            'target_utilization_days_label': result['target_utilization_days_label'] or '0 Hari',
                            'potential_to_target': result['potential_to_target'] or '',
                            'potential_to_target_with_icon': result['potential_to_target_with_icon'] or '',
                        })
                        records_created += 1
                    except Exception as e:
                        _logger.error(
                            f"Error creating record for vehicle {result['vehicle_id']}-{result['year']}-{result['month']}: {str(e)}")
                        continue

            self.env.cr.commit()

            if bulan_ini_only:
                _logger.info(
                    f"Successfully generated {records_created} records for current month ({current_year}-{current_month})")
            else:
                _logger.info(f"Successfully generated {records_created} records in data mart")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Data mart generated successfully! %s records created.') % records_created,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Error in generate_data_mart: {str(e)}")
            raise ValidationError(_("Error generating data mart: %s") % str(e))

    @api.model
    def cron_generate_data_mart(self):
        """
        Method untuk cron job - generate data mart
        Logika:
        - Jika tabel kosong → generate semua data
        - Jika tabel sudah ada → hapus data bulan ini lalu generate ulang data bulan ini
        """
        try:
            _logger.info("Starting cron job for data mart generation")

            # Cek apakah tabel kosong
            record_count = self.search_count([])

            if record_count == 0:
                # Tabel kosong, generate semua data
                _logger.info("Table is empty, generating all data via cron")
                self.generate_data_mart(bulan_ini_only=False)
            else:
                # Tabel sudah ada, generate ulang data bulan ini
                _logger.info("Table has data, regenerating current month data via cron")
                self.generate_data_mart(bulan_ini_only=True)

            _logger.info("Cron job for data mart generation completed successfully")

        except Exception as e:
            _logger.error(f"Error in cron_generate_data_mart: {str(e)}")
            # Tidak raise error agar cron tidak berhenti

    def action_refresh_data(self):
        """Action untuk refresh data dari UI"""
        return self.generate_data_mart(bulan_ini_only=True)

    def action_regenerate_all_data(self):
        """Action untuk regenerate semua data dari UI"""
        # Hapus semua data
        all_records = self.search([])
        if all_records:
            all_records.unlink()

        # Generate ulang semua data
        return self.generate_data_mart(bulan_ini_only=False)

    @api.model
    def get_vehicle_summary_by_category(self, year=None, month=None):
        """
        Method untuk mendapatkan summary per kategori
        (berguna jika masih diperlukan agregasi per kategori)
        """
        domain = []
        if year:
            domain.append(('year', '=', year))
        if month:
            domain.append(('month', '=', month))

        records = self.search(domain)

        # Group by category
        category_summary = {}
        for record in records:
            cat = record.category_name
            if cat not in category_summary:
                category_summary[cat] = {
                    'category_name': cat,
                    'actual_revenue': 0.0,
                    'target_revenue': 0.0,
                    'actual_utilization_days': 0,
                    'target_utilization_days': 0,
                    'vehicle_count': 0
                }

            category_summary[cat]['actual_revenue'] += record.actual_revenue
            category_summary[cat]['target_revenue'] += record.target_revenue
            category_summary[cat]['actual_utilization_days'] += record.actual_utilization_days
            category_summary[cat]['target_utilization_days'] += record.target_utilization_days
            category_summary[cat]['vehicle_count'] += 1

        # Calculate achievement for each category
        for cat_data in category_summary.values():
            if cat_data['target_revenue'] > 0:
                cat_data['achievement'] = round(
                    cat_data['actual_revenue'] / cat_data['target_revenue'], 2
                )
            else:
                cat_data['achievement'] = 0.0

        return list(category_summary.values())