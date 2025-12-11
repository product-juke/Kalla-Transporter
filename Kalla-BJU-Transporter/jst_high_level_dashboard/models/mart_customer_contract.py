from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MartCustomerContract(models.Model):
    _name = 'mart.customer.contract'
    _description = 'Customer Contract Data Mart'
    _order = 'contract_start_date desc, customer_name'

    # Fields matching the SQL query result
    contract_id = fields.Integer(
        string='Contract ID',
        required=True,
        help='ID of the original contract'
    )
    customer_id = fields.Integer(
        string='Customer ID',
        required=True,
        help='ID of the customer'
    )
    customer_name = fields.Char(
        string='Customer Name',
        required=True,
        help='Name of the customer'
    )
    contract_start_date = fields.Date(
        string='Contract Start Date',
        help='Start date of the contract'
    )
    contract_end_date = fields.Date(
        string='Contract End Date',
        help='End date of the contract'
    )
    is_contract_issue = fields.Boolean(
        string='Has Contract Issue',
        help='True if contract expires in 10 days or has already expired'
    )

    # Additional fields for data mart management
    last_updated = fields.Datetime(
        string='Last Updated',
        default=fields.Datetime.now,
        help='Timestamp when this record was last updated'
    )

    @api.model
    def generate_data_mart(self):
        """
        Generate data mart from the base tables.
        If table is empty, generate all data.
        If table has data, truncate and regenerate.
        """
        try:
            _logger.info("Starting data mart generation for mart.customer.contract")

            # Check if data exists
            existing_count = self.search_count([])

            # If data exists, delete all records first
            if existing_count > 0:
                _logger.info(f"Found {existing_count} existing records. Deleting all records.")
                self.search([]).unlink()

            # Execute the SQL query to get fresh data
            query = """
                SELECT
                    cc.id AS contract_id,
                    rp.id AS customer_id,
                    rp.name AS customer_name,
                    cc.start_date AS contract_start_date,
                    cc.end_date AS contract_end_date,
                    CASE 
                        WHEN cc.end_date - CURRENT_DATE <= 10 OR CURRENT_DATE > cc.end_date THEN true
                        ELSE false
                    END AS is_contract_issue
                FROM create_contract cc
                INNER JOIN res_partner rp ON rp.id = cc.partner_id
                ORDER BY cc.start_date DESC, rp.name;
            """

            self.env.cr.execute(query)
            results = self.env.cr.dictfetchall()

            if not results:
                _logger.warning("No data found from the query. Please check if create_contract table has data.")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Data Mart Generation'),
                        'message': _('No contract data found to generate data mart.'),
                        'type': 'warning',
                    }
                }

            # Create records in batch
            records_to_create = []
            for row in results:
                record_vals = {
                    'contract_id': row['contract_id'],
                    'customer_id': row['customer_id'],
                    'customer_name': row['customer_name'],
                    'contract_start_date': row['contract_start_date'],
                    'contract_end_date': row['contract_end_date'],
                    'is_contract_issue': row['is_contract_issue'],
                    'last_updated': fields.Datetime.now(),
                }
                records_to_create.append(record_vals)

            # Batch create all records
            created_records = self.create(records_to_create)

            _logger.info(f"Successfully created {len(created_records)} records in data mart")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Data Mart Generation Complete'),
                    'message': _('Successfully generated %s records in customer contract data mart.') % len(
                        created_records),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Error generating data mart: {str(e)}")
            raise UserError(_("Error generating data mart: %s") % str(e))

    @api.model
    def _cron_generate_data_mart(self):
        """
        Cron job method to automatically generate data mart.
        This method is called by the scheduled action.
        """
        try:
            _logger.info("Starting scheduled data mart generation")
            self.generate_data_mart()
            _logger.info("Scheduled data mart generation completed successfully")
        except Exception as e:
            _logger.error(f"Error in scheduled data mart generation: {str(e)}")
            # Re-raise the exception so the cron job is marked as failed
            raise

    def action_refresh_data_mart(self):
        """
        Action method to manually refresh data mart from UI.
        """
        return self.generate_data_mart()

    @api.model
    def get_contract_issues_summary(self):
        """
        Helper method to get summary of contract issues.
        Returns count of contracts with issues.
        """
        issue_count = self.search_count([('is_contract_issue', '=', True)])
        total_count = self.search_count([])

        return {
            'total_contracts': total_count,
            'contracts_with_issues': issue_count,
            'contracts_healthy': total_count - issue_count,
            'issue_percentage': round((issue_count / total_count * 100), 2) if total_count > 0 else 0
        }