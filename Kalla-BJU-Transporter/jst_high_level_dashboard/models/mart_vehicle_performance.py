from odoo import models, fields, api
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class MartVehiclePerformance(models.Model):
    _name = 'mart.vehicle.performance'
    _description = 'Vehicle Performance Data Mart'
    _order = 'category_name asc, year desc, month asc'
    _rec_name = 'vehicle_name_complete'

    # Vehicle Information
    vehicle_id = fields.Integer('Vehicle ID', required=True)
    vehicle_name = fields.Char('Vehicle Name')
    vehicle_name_complete = fields.Char('Vehicle Name Complete')
    no_lambung = fields.Char('No. Lambung')
    license_plate = fields.Char('License Plate')

    # Category Information
    category_id = fields.Integer('Category ID')
    category_name = fields.Char('Category Name')
    product_category_name = fields.Char('Product Category Name')
    product_category_complete_name = fields.Char('Product Category Complete Name')

    # Date Information
    year = fields.Integer('Year', required=True)
    month = fields.Integer('Month', required=True)
    date = fields.Date('Date')

    # Revenue & Target
    actual_revenue = fields.Float('Actual Revenue', digits=(16, 2))
    target_revenue = fields.Float('Target Revenue', digits=(16, 2))
    achievement = fields.Float('Achievement (%)', digits=(5, 2))

    # Utilization
    actual_utilization_days = fields.Float('Actual Utilization Days')
    target_utilization_days = fields.Float('Target Utilization Days')
    actual_utilization_days_label = fields.Char('Actual Utilization Days Label')
    target_utilization_days_label = fields.Char('Target Utilization Days Label')

    # Performance Indicators
    potential_to_target = fields.Char('Potential to Target')
    potential_to_target_with_icon = fields.Char('Potential to Target (with Icon)')

    # BOP & Cost Information
    bop_total = fields.Float('BOP Total', digits=(16, 2))
    rev_to_bop = fields.Float('Revenue to BOP Ratio', digits=(5, 2))
    cost_maintenance = fields.Float('Maintenance Cost', digits=(16, 2))
    fix_cost = fields.Float('Fixed Cost', digits=(16, 2))
    bop_biaya_tambahan = fields.Float('Additional BOP Cost', digits=(16, 2))

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart from complex SQL query

        Args:
            bulan_ini_only (bool): If True, only regenerate current month data
        """
        try:
            if bulan_ini_only:
                # Delete current month data
                current_month = datetime.now().month
                current_year = datetime.now().year
                self.search([
                    ('year', '=', current_year),
                    ('month', '=', current_month)
                ]).unlink()

                # Add WHERE clause for current month
                date_filter = f"AND vtl.year = {current_year} AND vtl.month = {current_month}"
            else:
                # Clear all existing data
                self.search([]).unlink()
                date_filter = ""

            # Main SQL query
            query = f"""
                SELECT
                    fv.id AS vehicle_id,
                    fv.vehicle_name,
                    fv.name AS vehicle_name_complete,
                    fv.no_lambung,
                    fv.license_plate,
                    fvmc.id AS category_id,
                    fvmc.name AS category_name,
                    pc.name AS product_category_name,
                    pc.complete_name AS product_category_complete_name,
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
                    END AS potential_to_target_with_icon,
                    SUM(sol.price_unit) AS bop_total,
                    ROUND(
                        CASE
                            WHEN SUM(sol.bop) <= 0 THEN 0
                            ELSE SUM(sol.price_unit) / SUM(sol.bop)
                        END,
                        2) AS rev_to_bop,
                    COALESCE(
                        (SELECT SUM(fvls2.amount * fvls2.qty)
                         FROM fleet_vehicle_log_services fvls2
                         WHERE fvls2.vehicle_id = fv.id
                         AND EXTRACT(MONTH FROM fvls2.date_in) = vtl.month
                         AND EXTRACT(YEAR FROM fvls2.date_in) = vtl.year), 0
                    ) AS cost_maintenance,
                    COALESCE(fv.fix_cost, 0) AS fix_cost,
                    COALESCE(
                        (SELECT SUM(fb.shipment + fb.tol_parkir + fb.buruh_muat_bongkar + fb.retribusi)
                         FROM fleet_bop fb
                         INNER JOIN fleet_do fd_bop ON fd_bop.category_id = fvmc.id
                         INNER JOIN sale_order_line sol_bop ON sol_bop.do_id = fd_bop.id
                         WHERE fb.origin_id = sol_bop.origin_id
                           AND fb.destination_id = sol_bop.destination_id
                           AND fb.total_bop = sol_bop.bop
                           AND EXTRACT(MONTH FROM fd_bop.date) = vtl.month
                           AND EXTRACT(YEAR FROM fd_bop.date) = vtl.year), 0
                    ) AS bop_biaya_tambahan
                FROM
                    fleet_vehicle fv
                    INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id
                    INNER JOIN fleet_do fd ON fd.vehicle_id = fv.id
                    INNER JOIN product_category pc ON pc.id = fd.product_category_id
                    INNER JOIN sale_order_line sol ON sol.do_id = fd.id
                    INNER JOIN vehicle_target_line vtl ON vtl.vehicle_id = fv.id
                WHERE 1=1 {date_filter}
                GROUP BY
                    fv.id,
                    fvmc.id,
                    fvmc.name,
                    vtl.year,
                    vtl.month,
                    pc.name,
                    pc.complete_name
                ORDER BY
                    fvmc.name ASC,
                    vtl.year DESC,
                    vtl.month ASC
            """

            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            # Insert data in batches for better performance
            batch_size = 100
            data_to_insert = []

            for result in results:
                data_to_insert.append({
                    'vehicle_id': result['vehicle_id'],
                    'vehicle_name': result['vehicle_name'],
                    'vehicle_name_complete': result['vehicle_name_complete'],
                    'no_lambung': result['no_lambung'],
                    'license_plate': result['license_plate'],
                    'category_id': result['category_id'],
                    'category_name': result['category_name'],
                    'product_category_name': result['product_category_name'],
                    'product_category_complete_name': result['product_category_complete_name'],
                    'year': result['year'],
                    'month': result['month'],
                    'date': result['date'],
                    'actual_revenue': result['actual_revenue'] or 0,
                    'target_revenue': result['target_revenue'] or 0,
                    'achievement': result['achievement'] or 0,
                    'actual_utilization_days': result['actual_utilization_days'] or 0,
                    'target_utilization_days': result['target_utilization_days'] or 0,
                    'actual_utilization_days_label': result['actual_utilization_days_label'],
                    'target_utilization_days_label': result['target_utilization_days_label'],
                    'potential_to_target': result['potential_to_target'],
                    'potential_to_target_with_icon': result['potential_to_target_with_icon'],
                    'bop_total': result['bop_total'] or 0,
                    'rev_to_bop': result['rev_to_bop'] or 0,
                    'cost_maintenance': result['cost_maintenance'] or 0,
                    'fix_cost': result['fix_cost'] or 0,
                    'bop_biaya_tambahan': result['bop_biaya_tambahan'] or 0,
                })

                if len(data_to_insert) >= batch_size:
                    self.create(data_to_insert)
                    data_to_insert = []

            # Insert remaining data
            if data_to_insert:
                self.create(data_to_insert)

            self.env.cr.commit()

            records_count = len(results)
            action_type = "current month" if bulan_ini_only else "all"
            _logger.info(f"Data mart generation completed: {records_count} records inserted for {action_type}")

            return {
                'success': True,
                'message': f'Successfully generated {records_count} records for {action_type}',
                'records_count': records_count
            }

        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Error generating data mart: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'records_count': 0
            }

    @api.model
    def cron_generate_data_mart(self):
        """
        Cron job method to generate data mart
        - If table is empty: generate all data
        - If table has data: regenerate current month only
        """
        try:
            existing_records = self.search_count([])

            if existing_records == 0:
                # Table is empty, generate all data
                result = self.generate_data_mart(bulan_ini_only=False)
                _logger.info("Cron: Generated all data for empty table")
            else:
                # Table has data, regenerate current month only
                result = self.generate_data_mart(bulan_ini_only=True)
                _logger.info("Cron: Regenerated current month data")

            return result

        except Exception as e:
            _logger.error(f"Cron job error: {str(e)}")
            return False

    def action_refresh_data(self):
        """Action method to refresh data mart manually"""
        result = self.generate_data_mart(bulan_ini_only=False)

        if result['success']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': result['message'],
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': result['message'],
                    'type': 'danger',
                    'sticky': True,
                }
            }