# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import datetime, timedelta
import logging
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

# === Notes ===:
# - Vehicle Mart Utilization = resource data nya dari function create dan write

class FleetDo(models.Model):
    _inherit = 'fleet.do'

    def action_update_post_do(self):
        if self.category_id.name != 'Self Drive':
            if not self.vehicle_id:
                raise UserError(_("Delivery Order has no Fleet"))
            elif not self.date:
                raise UserError(_("Delivery Order has no Delivery Date"))
        return super().action_update_post_do()

    def _update_utilization_do_no_tms(self, tms_do_id):
        """Update do_no_tms field in trx_vehicle_utilization records"""
        try:
            # Find all utilization records with matching do_id_lms
            utilization_records = self.env['trx.vehicle.utilization'].search([
                ('do_id_lms', '=', self.id)
            ])

            if utilization_records and len(utilization_records) > 0:
                # Update do_no_tms field for all matching records
                for utilization_record in utilization_records:
                    utilization_record.do_no_tms = tms_do_id

                _logger.info(f"=== DO ===> Updated {len(utilization_records)} utilization records with do_no_tms: {tms_do_id}")
            else:
                _logger.warning(f"=== DO ===> No utilization records found for DO ID: {self.id}")

        except Exception as e:
            _logger.error(f"=== DO ===> Error updating trx_vehicle_utilization: {str(e)}")
            # Don't raise the exception to prevent the main process from failing
            pass

    @api.model
    def post_data_to_TMS(self, data={}):
        result = super(FleetDo, self).post_data_to_TMS(data)

        # Update trx_vehicle_utilization records
        print('self.do_id', self.do_id)
        if self.do_id:
            self._update_utilization_do_no_tms(self.do_id)

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Create fleet DO records and their utilization data"""
        utilization_data_list = self._prepare_utilization_data_list(vals_list)
        records = super().create(vals_list)
        self._create_utilization_records(records, utilization_data_list)
        return records

    def _prepare_utilization_data_list(self, vals_list):
        """Prepare utilization data for all records to be created"""
        utilization_data_list = []

        for vals in vals_list:
            if self._should_create_utilization(vals):
                utilization_data = self._prepare_single_utilization_data(vals)
                if utilization_data:
                    utilization_data_list.append(utilization_data)

        return utilization_data_list

    def _should_create_utilization(self, vals):
        """Check if utilization records should be created for this record"""
        required_fields = ['date', 'po_line_ids', 'category_id']
        has_required_fields = all(field in vals for field in required_fields)
        has_lines = len(vals.get('po_line_ids', [])) > 0 or len(vals.get('line_ids', [])) > 0
        return has_required_fields and has_lines

    def _prepare_single_utilization_data(self, vals, line_ids_param=None):
        """Prepare utilization data for a single record"""
        line_ids = None
        date_value = None
        _logger.info(f"Values yang dikirim => {vals}")

        # Handle category_id - it could be an ID or a record object
        if line_ids_param:
            line_ids = line_ids_param
            # When called from external methods, category_id might be a record object
            if hasattr(vals['category_id'], 'id'):
                category_id = vals['category_id'].id
            else:
                category_id = vals['category_id']
        else:
            line_ids = self._get_line_ids(vals)
            category_id = vals['category_id']

        if not line_ids:
            return None

        max_distance_line, bop = self._find_max_distance_line_and_bop(line_ids, category_id)
        if not bop or not bop.total_cycle_time_day:
            return None

        # Handle date - it could be a string or date object
        date_value = vals.get('date') if not line_ids_param else vals.date
        if hasattr(date_value, 'strftime'):
            # It's a date/datetime object
            date_str = date_value.strftime('%Y-%m-%d')
        else:
            # It's already a string
            date_str = date_value

        date_strings = self._generate_date_strings(date_str, bop.total_cycle_time_day, line_ids, max_distance_line)
        related_objects = self._get_related_objects(vals, line_ids_param is not None)
        revenue_total = self._calculate_total_revenue(line_ids)

        return {
            'vals_index': 0,  # Will be set properly in the calling method
            'date_strings': date_strings,
            'vehicle_name': related_objects['vehicle'].name if related_objects['vehicle'] else None,
            'plate_no': related_objects['vehicle'].license_plate if related_objects['vehicle'] else None,
            'driver': related_objects['driver'].name if related_objects['driver'] else None,
            'category': related_objects['category'].name if related_objects['category'] else None,
            'customer': related_objects['customer'].name if related_objects['customer'] else None,
            'product_category': related_objects['product_category'].name if related_objects[
                'product_category'] else None,
        }

    def _get_line_ids(self, vals):
        """Extract line IDs from vals"""
        if len(vals.get('po_line_ids', [])) > 0:
            return [item[1] for item in vals['po_line_ids']]
        elif len(vals.get('line_ids', [])) > 0:
            return [item[1] for item in vals['line_ids']]
        return []

    def _find_max_distance_line_and_bop(self, line_ids, category_id):
        """Find the line with maximum distance and corresponding BOP"""
        max_distance = 0
        max_distance_line = None

        # Find line with maximum distance
        for line_id in line_ids:
            line = self.env['sale.order.line'].browse(line_id)
            if line.exists() and hasattr(line, 'distance') and line.distance:
                if line.distance > max_distance:
                    max_distance = line.distance
                    max_distance_line = line

        if not max_distance_line:
            return None, None

        # Find corresponding BOP
        bop = self.env['fleet.bop'].search([
            ('category_id', '=', category_id),
            ('origin_id', '=', max_distance_line.origin_id.id),
            ('destination_id', '=', max_distance_line.destination_id.id),
        ], limit=1)

        return max_distance_line, bop

    def _generate_date_strings(self, date, cycle_time, line_ids, max_distance_line):
        """Generate date strings for utilization records"""
        # Handle both string and date object inputs
        if isinstance(date, str):
            start_date = datetime.strptime(date, '%Y-%m-%d').date()
        elif hasattr(date, 'date') and callable(date.date):
            # Handle datetime object
            start_date = date.date()
        else:
            # Handle date object
            start_date = date

        date_strings = []
        temp_bop = None

        # for line_id in line_ids:
        #     line = self.env['sale.order.line'].browse(line_id)
        for i in range(cycle_time):
            current_date = start_date + timedelta(days=i)
            date_strings.append({
                'date': current_date.strftime('%Y-%m-%d'),
                # 'so_no': line.order_id.name,
                # 'bop': line.bop if line.id == max_distance_line.id and temp_bop != line.bop else None,
                # 'customer': line.order_id.partner_id.name,
                'so_no': '',
                'bop': '',
                'customer': '',
            })
            # temp_bop = line.bop

        return date_strings

    def _get_related_objects(self, vals, is_external_call=False):
        """Get related objects (vehicle, driver, category, etc.) from vals"""
        objects = {
            'vehicle': None,
            'driver': None,
            'category': None,
            'customer': None,
            'product_category': None,
        }

        # Handle vehicle_id
        if 'vehicle_id' in vals:
            if is_external_call and hasattr(vals['vehicle_id'], 'id'):
                # It's already a record object
                objects['vehicle'] = vals['vehicle_id']
            elif vals['vehicle_id']:
                # It's an ID
                objects['vehicle'] = self.env['fleet.vehicle'].browse(vals['vehicle_id'])

        # Handle driver_id
        if 'driver_id' in vals:
            if is_external_call and hasattr(vals['driver_id'], 'id'):
                # It's already a record object
                objects['driver'] = vals['driver_id']
            elif vals['driver_id']:
                # It's an ID
                objects['driver'] = self.env['res.partner'].browse(vals['driver_id'])

        # Handle category_id
        if 'category_id' in vals:
            if is_external_call and hasattr(vals['category_id'], 'id'):
                # It's already a record object
                objects['category'] = vals['category_id']
            elif vals['category_id']:
                # It's an ID
                objects['category'] = self.env['fleet.vehicle.model.category'].browse(vals['category_id'])

        # Handle partner_id
        if 'partner_id' in vals:
            if is_external_call and hasattr(vals['partner_id'], 'id'):
                # It's already a record object
                objects['customer'] = vals['partner_id']
            elif vals['partner_id']:
                # It's an ID
                objects['customer'] = self.env['res.partner'].browse(vals['partner_id'])

        # Handle product_category_id
        if 'product_category_id' in vals:
            if is_external_call and hasattr(vals['product_category_id'], 'id'):
                # It's already a record object
                objects['product_category'] = vals['product_category_id']
            elif vals['product_category_id']:
                # It's an ID
                objects['product_category'] = self.env['product.category'].browse(vals['product_category_id'])

        return objects

    def _calculate_total_revenue(self, line_ids):
        """Calculate total revenue from all lines"""
        revenue_total = 0
        for line_id in line_ids:
            line = self.env['sale.order.line'].browse(line_id)
            if line.exists():
                revenue_total += line.price_unit
        return revenue_total

    def _create_utilization_records(self, records, utilization_data_list):
        """Create utilization records for the created DO records"""
        for i, utilization_data in enumerate(utilization_data_list):
            record = records[i] if len(records) > 1 else records

            for date_info in utilization_data['date_strings']:
                self._create_single_utilization_record(record, utilization_data, date_info)

    def _create_single_utilization_record(self, record, utilization_data, date_info):
        longest_lines = record.po_line_ids.filtered(
            lambda l: (l.distance or 0) == max(record.po_line_ids.mapped('distance') or [])
        )
        print('longest_lines', longest_lines)
        """Create a single utilization record"""
        self.env['trx.vehicle.utilization'].sudo().create({
            'date': date_info['date'],
            'vehicle_name': utilization_data['vehicle_name'],
            'plate_no': utilization_data['plate_no'],
            'status_plan': 'UTILIZATION',
            'status_actual': None,
            'do_id_lms': record.id,
            'do_no_lms': record.name,
            'do_no_tms': None,
            'driver': utilization_data['driver'],
            'category': utilization_data['category'],
            'so_no': date_info['so_no'] or None,
            'customer': date_info['customer'] or None,
            # 'revenue': utilization_data['revenue'],
            'product': utilization_data['product_category'],
            # 'bop': date_info['bop'],
            'branch_project': longest_lines[0].order_id.branch_project if longest_lines and len(longest_lines) > 0 else None,
        })

    def write(self, vals):
        """Update fleet DO records and handle utilization data"""
        res = super().write(vals)

        vmu_records = self.env['trx.vehicle.utilization'].search([
            ('do_id_lms', '=', self.id)
        ])

        # Check if we need to handle utilization data for write operation
        if len(vmu_records) > 0 and self._should_handle_utilization_on_write(vals):
            self._handle_utilization_on_write(vals)

        return res

    def _should_handle_utilization_on_write(self, vals):
        """Check if utilization handling is needed on write"""
        # Check if date is being updated and we have required data
        date_updated = 'date' in vals
        fleet_updated = 'vehicle_id' in vals
        has_lines = len(self.po_line_ids) > 0 or len(self.line_ids) > 0
        has_category = bool(self.category_id)

        return (date_updated or fleet_updated) and has_lines and has_category

    def _handle_utilization_on_write(self, vals):
        """Handle utilization data creation/update on write"""

        # First, delete existing utilization records for this DO
        self._delete_existing_utilization_records()

        # Prepare data structure similar to create method
        current_vals = {
            'date': vals.get('date', self.date),
            'po_line_ids': [(6, 0, [line.id for line in self.po_line_ids])] if self.po_line_ids else [],
            'line_ids': [(6, 0, [line.id for line in self.line_ids])] if self.line_ids else [],
            'category_id': self.category_id.id,
            # 'vehicle_id': self.vehicle_id.id if self.vehicle_id else None,
            'vehicle_id': vals.get('vehicle_id', self.vehicle_id.id if self.vehicle_id else None),
            'driver_id': vals.get('driver_id', self.driver_id.id if self.driver_id else None),
            'partner_id': vals.get('partner_id', self.partner_id.id if self.partner_id else None),
            'product_category_id': vals.get('product_category_id', self.product_category_id.id if self.product_category_id else None),
        }

        # Use existing logic from create method
        if self._should_create_utilization(current_vals):
            utilization_data = self._prepare_single_utilization_data_for_write(current_vals)
            if utilization_data:
                self._create_utilization_records_for_write(utilization_data)

    def _delete_existing_utilization_records(self):
        """Delete existing utilization records for this DO"""
        try:
            # Find all utilization records with matching do_id_lms
            existing_records = self.env['trx.vehicle.utilization'].search([
                ('do_id_lms', '=', self.id)
            ])

            if existing_records:
                records_count = len(existing_records)
                existing_records.sudo().unlink()
                _logger.info(
                    f"=== DO WRITE ===> Deleted {records_count} existing utilization records for DO ID: {self.id}")
            else:
                _logger.info(f"=== DO WRITE ===> No existing utilization records found for DO ID: {self.id}")

        except Exception as e:
            _logger.error(f"=== DO WRITE ===> Error deleting existing utilization records: {str(e)}")
            # Don't raise the exception to prevent the main process from failing
            pass

    def _prepare_single_utilization_data_for_write(self, vals):
        """Prepare utilization data for write operation - adapted from create method"""
        line_ids = self._get_line_ids_for_write(vals)
        if not line_ids:
            return None

        max_distance_line, bop = self._find_max_distance_line_and_bop(line_ids, vals['category_id'])
        if not bop or not bop.total_cycle_time_day:
            return None

        date_strings = self._generate_date_strings(vals['date'], bop.total_cycle_time_day, line_ids, max_distance_line)
        related_objects = self._get_related_objects_for_write(vals)
        revenue_total = self._calculate_total_revenue(line_ids)

        return {
            'date_strings': date_strings,
            'vehicle_name': related_objects['vehicle'].name if related_objects['vehicle'] else None,
            'plate_no': related_objects['vehicle'].license_plate if related_objects['vehicle'] else None,
            'driver': related_objects['driver'].name if related_objects['driver'] else None,
            'category': related_objects['category'].name if related_objects['category'] else None,
            'customer': related_objects['customer'].name if related_objects['customer'] else None,
            # 'revenue': revenue_total / bop.total_cycle_time_day if bop.total_cycle_time_day and bop.total_cycle_time_day > 0 else None,
            'product_category': related_objects['product_category'].name if related_objects['product_category'] else None,
        }

    def _get_line_ids_for_write(self, vals):
        """Extract line IDs for write operation"""
        if vals.get('po_line_ids') and len(vals['po_line_ids']) > 0:
            # For write operation, po_line_ids might be in different format
            if vals['po_line_ids'][0][0] == 6:  # (6, 0, [ids])
                return vals['po_line_ids'][0][2]
        elif vals.get('line_ids') and len(vals['line_ids']) > 0:
            if vals['line_ids'][0][0] == 6:  # (6, 0, [ids])
                return vals['line_ids'][0][2]
        return []

    def _get_related_objects_for_write(self, vals):
        """Get related objects for write operation"""
        objects = {
            'vehicle': None,
            'driver': None,
            'category': None,
            'customer': None,
            'product_category': None,
        }

        if vals.get('vehicle_id'):
            objects['vehicle'] = self.env['fleet.vehicle'].browse(vals['vehicle_id'])

        if vals.get('driver_id'):
            objects['driver'] = self.env['res.partner'].browse(vals['driver_id'])

        if vals.get('category_id'):
            objects['category'] = self.env['fleet.vehicle.model.category'].browse(vals['category_id'])

        if vals.get('partner_id'):
            objects['customer'] = self.env['res.partner'].browse(vals['partner_id'])

        if vals.get('product_category_id'):
            objects['product_category'] = self.env['product.category'].browse(vals['product_category_id'])

        return objects

    def _create_utilization_records_for_write(self, utilization_data):
        """Create utilization records for write operation"""
        longest_lines = self.po_line_ids.filtered(
            lambda l: (l.distance or 0) == max(self.po_line_ids.mapped('distance') or [])
        )
        for date_info in utilization_data['date_strings']:
            self.env['trx.vehicle.utilization'].sudo().create({
                'date': date_info['date'],
                'vehicle_name': utilization_data['vehicle_name'],
                'plate_no': utilization_data['plate_no'],
                'status_plan': 'UTILIZATION',
                'status_actual': None,
                'do_id_lms': self.id,
                'do_no_lms': self.name,
                'do_no_tms': self.do_id or None,
                'driver': utilization_data['driver'],
                'category': utilization_data['category'],
                'so_no': date_info['so_no'] or None,
                'customer': date_info['customer'] or None,
                # 'revenue': utilization_data['revenue'],
                'product': utilization_data['product_category'],
                # 'bop': date_info['bop'],
                'branch_project': longest_lines[0].order_id.branch_project if longest_lines and len(longest_lines) > 0 else None            })

    def unlink(self):
        """Override unlink to delete related utilization records when DO is deleted"""
        # Store DO IDs before deletion for logging
        do_ids = self.ids
        do_names = [record.name for record in self]

        # Delete related utilization records for each DO
        for record in self:
            try:
                # Find all utilization records with matching do_id_lms
                utilization_records = self.env['trx.vehicle.utilization'].search([
                    ('do_id_lms', '=', record.id),
                    # ('date', '=', record.date),
                ])

                if utilization_records:
                    records_count = len(utilization_records)
                    utilization_records.sudo().unlink()
                    _logger.info(
                        f"=== DO DELETE ===> Deleted {records_count} utilization records for DO ID: {record.id} (Name: {record.name})")
                else:
                    _logger.info(
                        f"=== DO DELETE ===> No utilization records found for DO ID: {record.id} (Name: {record.name})")

            except Exception as e:
                _logger.error(
                    f"=== DO DELETE ===> Error deleting utilization records for DO ID: {record.id}: {str(e)}")
                # Continue with the deletion process even if utilization cleanup fails
                pass

        # Call parent unlink method to delete the DO records
        result = super().unlink()

        _logger.info(f"=== DO DELETE ===> Successfully deleted DO records: {do_names}")

        return result