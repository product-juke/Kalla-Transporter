from odoo import models, fields, api
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class MartStatusVehicle(models.Model):
    _name = 'mart.status.vehicle'
    _description = 'Vehicle Status Data Mart'
    _order = 'vehicle_name asc'
    _rec_name = 'vehicle_name'

    # Fields matching the query results
    vehicle_code = fields.Char(string='Vehicle Code')
    vehicle_name = fields.Char(string='Vehicle Name')
    license_plate = fields.Char(string='License Plate')
    no_lambung = fields.Char(string='No Lambung')
    status = fields.Char(string='Status')
    status_desc = fields.Char(string='Status Description')
    product_category_name = fields.Char(string='Product Category')
    vehicle_category_name = fields.Char(string='Vehicle Category')

    # Additional fields for tracking
    last_update = fields.Datetime(string='Last Update', default=fields.Datetime.now)
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Fleet Vehicle', ondelete='cascade')

    # New fields for monthly tracking
    insert_month = fields.Integer(string='Insert Month', help='Month when record was inserted (1-12)')
    insert_year = fields.Integer(string='Insert Year', help='Year when record was inserted')
    insert_date = fields.Date(string='Insert Date', default=fields.Date.today, help='Date when record was inserted')

    @api.model
    def generate_data_mart(self, bulan_ini_only=False):
        """
        Generate data mart from fleet vehicle data

        Args:
            bulan_ini_only (bool): If True, only regenerate current month data
        """
        try:
            current_date = date.today()
            current_month = current_date.month
            current_year = current_date.year

            if bulan_ini_only:
                # Delete only current month records
                current_month_records = self.search([
                    ('insert_month', '=', current_month),
                    ('insert_year', '=', current_year)
                ])
                if current_month_records:
                    current_month_records.unlink()
                    _logger.info(f"Cleared {len(current_month_records)} records for {current_month}/{current_year}")
            else:
                # Clear all existing data if regenerating completely
                if self.search_count([]) > 0:
                    _logger.info("Clearing all existing data mart records")
                    self.search([]).unlink()

            # Execute the query
            query = """
                SELECT
                    fv.id as fleet_vehicle_id,
                    fv.name as vehicle_code,
                    fv.vehicle_name,
                    fv.license_plate,
                    fv.no_lambung,
                    fv.vehicle_status as status,
                    (
                        CASE
                            WHEN UPPER(fvs.name_description) IN ('DRIVER NOT', 'DRIVER NOT READY') 
                                THEN 'DRIVER NOT READY'
                            WHEN UPPER(fvs.name_description) IN ('LICENSE NOT', 'LICENSE NOT READY') 
                                THEN 'LICENSE NOT READY'
                            WHEN UPPER(fvs.name_description) LIKE 'DELAY%' THEN 'DELAY'
                            WHEN UPPER(fvs.name_description) = 'ON DELIVERY' THEN 'ON DELIVERY'
                            ELSE UPPER(fvs.name_description)
                        END
                    ) as status_desc,
                    pc.name as product_category_name,
                    fvmc.name as vehicle_category_name
                FROM fleet_vehicle fv
                INNER JOIN fleet_vehicle_status fvs ON fvs.id = fv.last_status_description_id 
                INNER JOIN product_category pc ON pc.id = fv.product_category_id 
                INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id 
                WHERE fv.vehicle_status IS NOT NULL
                ORDER BY fv.name ASC
            """

            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            # Prepare data for batch creation
            data_to_create = []
            current_datetime = fields.Datetime.now()

            for row in results:
                # Skip if bulan_ini_only=True and record already exists for current month
                if bulan_ini_only:
                    existing_current_month = self.search([
                        ('fleet_vehicle_id', '=', row.get('fleet_vehicle_id')),
                        ('insert_month', '=', current_month),
                        ('insert_year', '=', current_year)
                    ])
                    if existing_current_month:
                        continue

                data_to_create.append({
                    'fleet_vehicle_id': row.get('fleet_vehicle_id'),
                    'vehicle_code': row.get('vehicle_code'),
                    'vehicle_name': row.get('vehicle_name'),
                    'license_plate': row.get('license_plate'),
                    'no_lambung': row.get('no_lambung'),
                    'status': row.get('status'),
                    'status_desc': row.get('status_desc'),
                    'product_category_name': row.get('product_category_name'),
                    'vehicle_category_name': row.get('vehicle_category_name'),
                    'last_update': current_datetime,
                    'insert_month': current_month,
                    'insert_year': current_year,
                    'insert_date': current_date,
                })

            # Batch create records
            if data_to_create:
                self.create(data_to_create)
                action_type = "current month" if bulan_ini_only else "all"
                _logger.info(f"Successfully generated {len(data_to_create)} {action_type} data mart records")
            else:
                _logger.warning("No data found to generate data mart")

            return True

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            return False

    @api.model
    def update_data_mart(self):
        """Update existing data mart records based on changed fleet vehicles"""
        try:
            current_date = date.today()
            current_month = current_date.month
            current_year = current_date.year

            # Get all current fleet vehicle data
            query = """
                SELECT
                    fv.id as fleet_vehicle_id,
                    fv.name as vehicle_code,
                    fv.vehicle_name,
                    fv.license_plate,
                    fv.no_lambung,
                    fv.vehicle_status as status,
                    (
                        CASE
                            WHEN UPPER(fvs.name_description) IN ('DRIVER NOT', 'DRIVER NOT READY') 
                                THEN 'DRIVER NOT READY'
                            WHEN UPPER(fvs.name_description) IN ('LICENSE NOT', 'LICENSE NOT READY') 
                                THEN 'LICENSE NOT READY'
                            WHEN UPPER(fvs.name_description) LIKE 'DELAY%' THEN 'DELAY'
                            WHEN UPPER(fvs.name_description) = 'ON DELIVERY' THEN 'ON DELIVERY'
                            ELSE UPPER(fvs.name_description)
                        END
                    ) as status_desc,
                    pc.name as product_category_name,
                    fvmc.name as vehicle_category_name
                FROM fleet_vehicle fv
                INNER JOIN fleet_vehicle_status fvs ON fvs.id = fv.last_status_description_id 
                INNER JOIN product_category pc ON pc.id = fv.product_category_id 
                INNER JOIN fleet_vehicle_model_category fvmc ON fvmc.id = fv.category_id 
                WHERE fv.vehicle_status IS NOT NULL
                ORDER BY fv.name ASC
            """

            self.env.cr.execute(query)
            current_data = {row['fleet_vehicle_id']: row for row in self.env.cr.dictfetchall()}

            # Get existing data mart records for current month
            existing_records = self.search([
                ('insert_month', '=', current_month),
                ('insert_year', '=', current_year)
            ])
            existing_vehicle_ids = set(existing_records.mapped('fleet_vehicle_id').ids)
            current_vehicle_ids = set(current_data.keys())

            # Find records to delete (vehicles no longer exist or don't meet criteria)
            to_delete_ids = existing_vehicle_ids - current_vehicle_ids
            if to_delete_ids:
                records_to_delete = existing_records.filtered(lambda r: r.fleet_vehicle_id.id in to_delete_ids)
                records_to_delete.unlink()
                _logger.info(f"Deleted {len(records_to_delete)} obsolete records for current month")

            # Find records to create (new vehicles for current month)
            to_create_ids = current_vehicle_ids - existing_vehicle_ids
            data_to_create = []
            current_datetime = fields.Datetime.now()

            for vehicle_id in to_create_ids:
                row = current_data[vehicle_id]
                data_to_create.append({
                    'fleet_vehicle_id': row.get('fleet_vehicle_id'),
                    'vehicle_code': row.get('vehicle_code'),
                    'vehicle_name': row.get('vehicle_name'),
                    'license_plate': row.get('license_plate'),
                    'no_lambung': row.get('no_lambung'),
                    'status': row.get('status'),
                    'status_desc': row.get('status_desc'),
                    'product_category_name': row.get('product_category_name'),
                    'vehicle_category_name': row.get('vehicle_category_name'),
                    'last_update': current_datetime,
                    'insert_month': current_month,
                    'insert_year': current_year,
                    'insert_date': current_date,
                })

            if data_to_create:
                self.create(data_to_create)
                _logger.info(f"Created {len(data_to_create)} new records for current month")

            # Update existing records for current month
            updated_count = 0
            for record in existing_records.filtered(lambda r: r.fleet_vehicle_id.id in current_vehicle_ids):
                current_row = current_data[record.fleet_vehicle_id.id]
                update_vals = {}

                # Check each field for changes
                fields_to_check = [
                    ('vehicle_code', 'vehicle_code'),
                    ('vehicle_name', 'vehicle_name'),
                    ('license_plate', 'license_plate'),
                    ('no_lambung', 'no_lambung'),
                    ('status', 'status'),
                    ('status_desc', 'status_desc'),
                    ('product_category_name', 'product_category_name'),
                    ('vehicle_category_name', 'vehicle_category_name'),
                ]

                for field_name, data_key in fields_to_check:
                    if getattr(record, field_name) != current_row.get(data_key):
                        update_vals[field_name] = current_row.get(data_key)

                if update_vals:
                    update_vals['last_update'] = current_datetime
                    record.write(update_vals)
                    updated_count += 1

            if updated_count > 0:
                _logger.info(f"Updated {updated_count} existing records for current month")

            return True

        except Exception as e:
            _logger.error(f"Error updating data mart: {str(e)}")
            return False

    @api.model
    def cron_sync_data_mart(self, bulan_ini_only=False):
        """
        Cron job method to sync data mart

        Args:
            bulan_ini_only (bool): If True, only sync current month data
        """
        current_date = date.today()
        current_month = current_date.month
        current_year = current_date.year

        _logger.info(f"Starting data mart synchronization (bulan_ini_only={bulan_ini_only})")

        if bulan_ini_only:
            # Check if current month data exists
            current_month_count = self.search_count([
                ('insert_month', '=', current_month),
                ('insert_year', '=', current_year)
            ])

            _logger.info(f"Regenerating data for current month {current_month}/{current_year}")
            result = self.generate_data_mart(bulan_ini_only=True)

        else:
            # Check if table is empty
            total_count = self.search_count([])

            if total_count == 0:
                _logger.info("Data mart is empty, generating all data")
                result = self.generate_data_mart(bulan_ini_only=False)
            else:
                _logger.info(f"Data mart has {total_count} records, performing update")
                result = self.update_data_mart()

        if result:
            _logger.info("Data mart synchronization completed successfully")
        else:
            _logger.error("Data mart synchronization failed")

        return result

    @api.model
    def get_monthly_summary(self):
        """Get summary of data mart records by month and year"""
        query = """
            SELECT 
                insert_year,
                insert_month,
                COUNT(*) as record_count,
                MIN(insert_date) as first_insert,
                MAX(last_update) as last_update
            FROM mart_status_vehicle 
            GROUP BY insert_year, insert_month 
            ORDER BY insert_year DESC, insert_month DESC
        """

        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    @api.model
    def cleanup_old_months(self, months_to_keep=6):
        """
        Clean up old monthly data, keeping only the specified number of months

        Args:
            months_to_keep (int): Number of recent months to keep
        """
        try:
            current_date = date.today()

            # Get list of months to delete
            query = """
                SELECT DISTINCT insert_year, insert_month, COUNT(*) as count
                FROM mart_status_vehicle 
                GROUP BY insert_year, insert_month 
                ORDER BY insert_year DESC, insert_month DESC 
                OFFSET %s
            """

            self.env.cr.execute(query, (months_to_keep,))
            months_to_delete = self.env.cr.dictfetchall()

            total_deleted = 0
            for month_data in months_to_delete:
                records_to_delete = self.search([
                    ('insert_year', '=', month_data['insert_year']),
                    ('insert_month', '=', month_data['insert_month'])
                ])

                if records_to_delete:
                    count = len(records_to_delete)
                    records_to_delete.unlink()
                    total_deleted += count
                    _logger.info(
                        f"Deleted {count} records for {month_data['insert_month']}/{month_data['insert_year']}")

            if total_deleted > 0:
                _logger.info(f"Cleanup completed: {total_deleted} total records deleted")
            else:
                _logger.info("No old records to cleanup")

            return True

        except Exception as e:
            _logger.error(f"Error during cleanup: {str(e)}")
            return False