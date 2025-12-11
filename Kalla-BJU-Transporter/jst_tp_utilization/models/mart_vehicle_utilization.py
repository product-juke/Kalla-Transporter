from odoo import fields, models, api, _
from datetime import datetime, timedelta
import logging
from odoo.exceptions import UserError
import calendar


_logger = logging.getLogger(__name__)


class MartVehicleUtilization(models.Model):
    _name = 'mart.vehicle.utilization'

    date = fields.Date()
    license_plate = fields.Char()

    status = fields.Char(
        string='Status'
    )
    vehicle_name = fields.Char()
    vehicle_id = fields.Integer()
    category = fields.Char()
    type = fields.Char()
    customer = fields.Char()
    # revenue = fields.Float()
    invoice_no = fields.Char()
    # bop = fields.Float()
    branch_project = fields.Char()

    def insert_data_mart_to_staging_table(self):
        _logger.info('Job Insert Data Mart (Staging) is running')

        # Mendapatkan tanggal hari ini
        today = datetime.now().date()

        # Mendapatkan awal dan akhir bulan ini
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        try:
            # Menghapus data pada bulan ini
            records_to_delete = self.search([
                ('date', '>=', start_of_month),
                ('date', '<=', end_of_month)
            ])

            if records_to_delete:
                deleted_count = len(records_to_delete)
                records_to_delete.unlink()
                _logger.info(f'Deleted {deleted_count} records for current month ({start_of_month} to {end_of_month})')
            else:
                _logger.info(f'No records found to delete for current month ({start_of_month} to {end_of_month})')

            # insert data baru
            self._insert_new_data()

            _logger.info('Job Insert Data Mart (Staging) completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_to_staging_table: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart: %s') % str(e))

    def _insert_new_data(self):
        """
        Insert data dari trx.vehicle.utilization dan trx.vehicle.non.utilization
        ke dalam mart.vehicle.utilization.

        Logika:
        - Jika tabel mart kosong: insert semua data yang tersedia
        - Jika tabel sudah ada data: hapus data bulan ini dan insert ulang data bulan ini

        Data dengan create_date terbaru akan digunakan jika ada duplikasi tanggal dan plat nomor.
        Untuk sisa hari yang tidak ada data, akan dibuat dengan status "READY FOR USE".
        """
        try:
            # Mendapatkan tanggal hari ini
            today = datetime.now().date()

            # Check apakah tabel mart masih kosong
            existing_mart_count = self.search_count([])
            is_empty_table = existing_mart_count == 0

            if is_empty_table:
                _logger.info('Mart table is empty. Will insert all available data.')
                # Jika tabel kosong, ambil semua data yang tersedia
                start_date = None  # Tidak ada batasan tanggal
                end_date = None
            else:
                _logger.info('Mart table has existing data. Will delete and re-insert current month data.')
                # Jika sudah ada data, fokus pada bulan ini saja
                start_date = today.replace(day=1)
                if today.month == 12:
                    end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

                _logger.info(f'Processing data for current month: {start_date} to {end_date}')

                # Hapus data bulan ini yang sudah ada
                existing_current_month = self.search([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ])
                if existing_current_month:
                    existing_current_month.unlink()
                    _logger.info(f'Deleted {len(existing_current_month)} existing records for current month')

            # Dictionary untuk menyimpan data dengan create_date terbaru
            # Key: "date-license_plate", Value: {'data': mart_data, 'create_date': datetime}
            final_data_map = {}

            # Step 1: Process data dari trx.vehicle.utilization
            utilization_domain = []
            if not is_empty_table:  # Jika tidak kosong, filter berdasarkan bulan ini
                utilization_domain = [
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ]

            utilization_records = self.env['trx.vehicle.utilization'].search(utilization_domain)
            _logger.info(f'Found {len(utilization_records)} utilization records')

            for record in utilization_records:
                # Determine status priority: actual jika ada, jika tidak maka plan
                status = record.status_actual or record.status_plan
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', record.plate_no),
                    ('name', '=', record.vehicle_name),
                ], limit=1)

                mart_data = {
                    'date': record.date,
                    'license_plate': record.plate_no,
                    'status': status,
                    'vehicle_name': record.vehicle_name,
                    'vehicle_id': vehicle.id if vehicle else None,
                    'category': record.category,
                    'type': vehicle.category_id.product_category_id.name if vehicle and vehicle.category_id and vehicle.category_id.product_category_id else '',
                    'customer': record.customer,
                    'invoice_no': record.invoice_no,
                    'branch_project': record.branch_project,
                }

                key = f"{record.date}-{record.plate_no}"

                # Jika key belum ada atau create_date lebih baru, simpan/update data
                if key not in final_data_map or record.create_date > final_data_map[key]['create_date']:
                    final_data_map[key] = {
                        'data': mart_data,
                        'create_date': record.create_date,
                        'source': 'utilization'
                    }
                    _logger.info(
                        f'Added/Updated utilization data for {record.plate_no} on {record.date} (create_date: {record.create_date})')

            # Step 2: Process data dari trx.vehicle.non.utilization
            non_utilization_domain = []
            if not is_empty_table:  # Jika tidak kosong, filter berdasarkan bulan ini
                non_utilization_domain = [
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ]

            non_utilization_records = self.env['trx.vehicle.non.utilization'].search(non_utilization_domain)
            _logger.info(f'Found {len(non_utilization_records)} non-utilization records')

            for record in non_utilization_records:
                # Determine status priority: actual jika ada, jika tidak maka plan
                status = record.status_actual or record.status_plan
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', record.plate_no),
                    ('name', '=', record.vehicle_name),
                ], limit=1)

                mart_data = {
                    'date': record.date,
                    'license_plate': record.plate_no,
                    'status': status,
                    'vehicle_name': record.vehicle_name,
                    'vehicle_id': vehicle.id if vehicle else None,
                    'category': record.category,
                    'type': vehicle.category_id.product_category_id.name if vehicle and vehicle.category_id and vehicle.category_id.product_category_id else '',
                    'customer': record.customer,
                    'invoice_no': record.invoice_no,
                    'branch_project': record.branch_project,
                }

                key = f"{record.date}-{record.plate_no}"

                # Jika key belum ada atau create_date lebih baru, simpan/update data
                if key not in final_data_map or record.create_date > final_data_map[key]['create_date']:
                    if key in final_data_map:
                        _logger.info(
                            f'Replaced {final_data_map[key]["source"]} data with non-utilization for {record.plate_no} on {record.date} '
                            f'(non-util create_date: {record.create_date} > previous create_date: {final_data_map[key]["create_date"]})')
                    else:
                        _logger.info(
                            f'Added new non-utilization data for {record.plate_no} on {record.date} (create_date: {record.create_date})')

                    final_data_map[key] = {
                        'data': mart_data,
                        'create_date': record.create_date,
                        'source': 'non-utilization'
                    }

            # Step 3: Tambahkan data "READY FOR USE" untuk sisa hari yang belum ada data
            # Hanya untuk bulan ini atau semua periode jika tabel kosong
            if is_empty_table:
                # Jika tabel kosong, kita perlu menentukan range tanggal untuk "READY FOR USE"
                # Ambil tanggal minimum dan maksimum dari data yang ada
                if final_data_map:
                    # Extract tanggal dari key format "YYYY-MM-DD-license_plate"
                    dates_in_data = []
                    for key in final_data_map.keys():
                        # Key format: "YYYY-MM-DD-license_plate"
                        # Split by '-' dan ambil 3 bagian pertama untuk tanggal
                        key_parts = key.split('-')
                        if len(key_parts) >= 3:
                            date_str = f"{key_parts[0]}-{key_parts[1]}-{key_parts[2]}"
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                                dates_in_data.append(date_obj)
                            except ValueError as ve:
                                _logger.warning(
                                    f'Invalid date format in key: {key}, extracted: {date_str}, error: {ve}')
                                continue

                    if dates_in_data:
                        min_date = min(dates_in_data)
                        max_date = max(dates_in_data)
                        # Extend ke awal dan akhir bulan untuk tanggal min dan max
                        fill_start = min_date.replace(day=1)
                        if max_date.month == 12:
                            fill_end = max_date.replace(year=max_date.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            fill_end = max_date.replace(month=max_date.month + 1, day=1) - timedelta(days=1)
                    else:
                        # Jika tidak bisa parse tanggal, gunakan bulan ini
                        fill_start = today.replace(day=1)
                        if today.month == 12:
                            fill_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            fill_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
                else:
                    # Jika tidak ada data sama sekali, gunakan bulan ini
                    fill_start = today.replace(day=1)
                    if today.month == 12:
                        fill_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        fill_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            else:
                fill_start = start_date
                fill_end = end_date

            self._fill_missing_dates_with_ready_status(final_data_map, fill_start, fill_end)

            # Step 4: Extract final data list untuk bulk insert
            mart_data_list = [item['data'] for item in final_data_map.values()]

            # Step 5: Bulk insert semua data ke mart table
            if mart_data_list:
                self.create(mart_data_list)
                operation_type = "all available data" if is_empty_table else "current month data"
                _logger.info(f'Successfully inserted {len(mart_data_list)} unique records to mart.vehicle.utilization ({operation_type})')

                # Log summary
                utilization_count = sum(1 for item in final_data_map.values() if item['source'] == 'utilization')
                non_utilization_count = sum(1 for item in final_data_map.values() if item['source'] == 'non-utilization')
                ready_for_use_count = sum(1 for item in final_data_map.values() if item['source'] == 'ready_for_use')
                _logger.info(
                    f'Summary: {utilization_count} from utilization, {non_utilization_count} from non-utilization, {ready_for_use_count} ready for use')
            else:
                _logger.info('No data to insert')

        except Exception as e:
            _logger.error(f'Error in _insert_new_data: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memasukkan data baru: %s') % str(e))

    def _fill_missing_dates_with_ready_status(self, final_data_map, start_of_month, end_of_month):
        """
        Mengisi tanggal yang hilang dengan status "READY FOR USE" untuk setiap license plate yang sudah ada.
        """
        try:
            # Mendapatkan semua license plate yang sudah ada dalam data
            existing_license_plates = set()
            for key, value in final_data_map.items():
                existing_license_plates.add(value['data']['license_plate'])

            _logger.info(f'Found {len(existing_license_plates)} unique license plates: {existing_license_plates}')

            # Generate semua tanggal dalam bulan ini
            current_date = start_of_month
            all_dates = []
            while current_date <= end_of_month:
                all_dates.append(current_date)
                current_date += timedelta(days=1)

            _logger.info(f'Generated {len(all_dates)} dates from {start_of_month} to {end_of_month}')

            # Untuk setiap license plate, cek apakah ada data untuk setiap tanggal
            ready_for_use_count = 0
            for license_plate in existing_license_plates:
                # Cari vehicle info untuk license plate ini
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', license_plate)
                ], limit=1)

                # Cari data utilization atau non-utilization untuk mendapatkan info vehicle
                sample_utilization = self.env['trx.vehicle.utilization'].search([
                    ('plate_no', '=', license_plate)
                ], limit=1)

                sample_non_utilization = self.env['trx.vehicle.non.utilization'].search([
                    ('plate_no', '=', license_plate)
                ], limit=1)

                # Ambil info vehicle dari sample yang ada
                vehicle_name = ''
                category = ''
                if sample_utilization:
                    vehicle_name = sample_utilization.vehicle_name
                    category = sample_utilization.category
                elif sample_non_utilization:
                    vehicle_name = sample_non_utilization.vehicle_name
                    category = sample_non_utilization.category
                elif vehicle:
                    vehicle_name = vehicle.name
                    category = vehicle.category_id.name if vehicle.category_id else ''

                for date in all_dates:
                    key = f"{date}-{license_plate}"

                    # Jika tanggal ini belum ada data untuk license plate ini
                    if key not in final_data_map:
                        vehicle_data = self.env['fleet.vehicle'].search([
                            ('license_plate', '=', license_plate)
                        ], limit=1)
                        mart_data = {
                            'date': date,
                            'license_plate': license_plate,
                            'status': 'READY FOR USE',
                            'vehicle_name': vehicle_name,
                            'vehicle_id': vehicle_data.id if vehicle_data else None,
                            'category': category,
                            'type': vehicle.category_id.product_category_id.name if vehicle and vehicle.category_id and vehicle.category_id.product_category_id else '',
                            'customer': '',
                            'invoice_no': '',
                            'branch_project': None,
                        }

                        final_data_map[key] = {
                            'data': mart_data,
                            'create_date': datetime.now(),
                            'source': 'ready_for_use'
                        }
                        ready_for_use_count += 1

            _logger.info(f'Added {ready_for_use_count} "READY FOR USE" records for missing dates')

        except Exception as e:
            _logger.error(f'Error in _fill_missing_dates_with_ready_status: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat mengisi tanggal yang hilang: %s') % str(e))

class MartVehicleUtilizationSmry(models.Model):
    _name = 'mart.vehicle.utilization.smry'
    # _log_access = False

    year = fields.Integer()
    month = fields.Integer()
    category = fields.Char(string="Vehicle Model Category")
    license_plate = fields.Char(string="Plat Nomor")
    status = fields.Char()
    total = fields.Integer()
    type = fields.Char()
    month_name = fields.Char()
    total_target_util = fields.Char()
    formatted_date = fields.Date()

    def get_month_name_indonesian(self, month_number):
        """Fungsi untuk mengkonversi nomor bulan ke nama bulan dalam bahasa Indonesia"""
        month_names = {
            1: 'Januari',
            2: 'Februari',
            3: 'Maret',
            4: 'April',
            5: 'Mei',
            6: 'Juni',
            7: 'Juli',
            8: 'Agustus',
            9: 'September',
            10: 'Oktober',
            11: 'November',
            12: 'Desember'
        }
        return month_names.get(month_number, '')

    def create_custom_date(self, year, month):
        """Fungsi untuk membuat datetime berdasarkan year + month + tanggal 1 + jam sekarang"""
        current_time = datetime.now()
        try:
            # Buat datetime dengan year dan month dari data, tanggal 1, dan jam sekarang
            custom_date = datetime(
                year=year,
                month=month,
                day=1,
                hour=current_time.hour,
                minute=current_time.minute,
                second=current_time.second,
                microsecond=current_time.microsecond
            )
            return custom_date
        except ValueError as e:
            _logger.error(f'Error creating custom date for year {year}, month {month}: {str(e)}')
            return datetime.now()

    def insert_data_mart_summary(self):
        """
        Insert data summary dari mart.vehicle.utilization ke mart.vehicle.utilization.smry
        untuk bulan ini dengan grouping berdasarkan year, month, category, license_plate, status, type
        """
        _logger.info('Job Insert Data Mart Summary is running')

        try:
            # Mendapatkan tanggal hari ini
            today = datetime.now().date()
            current_year = today.year
            current_month = today.month
            month_name = self.get_month_name_indonesian(current_month)
            custom_create_date = self.create_custom_date(current_year, current_month)

            # Mendapatkan awal dan akhir bulan ini
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

            _logger.info(f'Processing summary for period: {start_of_month} to {end_of_month}')

            # Menghapus data summary untuk bulan ini
            summary_records_to_delete = self.search([
                ('year', '=', current_year),
                ('month', '=', current_month)
            ])

            if summary_records_to_delete:
                deleted_count = len(summary_records_to_delete)
                summary_records_to_delete.unlink()
                _logger.info(f'Deleted {deleted_count} summary records for {current_year}-{current_month:02d}')
            else:
                _logger.info(f'No summary records found to delete for {current_year}-{current_month:02d}')

            # Mengambil data dari mart.vehicle.utilization untuk bulan ini
            mart_records = self.env['mart.vehicle.utilization'].search([
                ('date', '>=', start_of_month),
                ('date', '<=', end_of_month)
            ])

            if len(self.search([])) <= 0:
                mart_records = self.env['mart.vehicle.utilization'].search([])

            if not mart_records:
                _logger.info('No mart records found for current month')
                return

            _logger.info(f'Found {len(mart_records)} mart records to process')

            # Grouping data berdasarkan kombinasi: category, license_plate, status, type
            grouped_data = {}

            for record in mart_records:
                # Create key untuk grouping
                key = (
                    record.category or '',
                    record.license_plate or '',
                    record.status or '',
                    record.type or ''
                )

                if key not in grouped_data:
                    grouped_data[key] = {
                        'category': record.category,
                        'license_plate': record.license_plate,
                        'status': record.status,
                        'type': record.type,
                        'total': 0
                    }

                # Increment total count
                grouped_data[key]['total'] += 1

            # Prepare data untuk insert ke summary table
            summary_data_list = []
            for key, data in grouped_data.items():
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', data['license_plate'])
                ], limit=1)
                vehicle_target = self.env['vehicle.target.line'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('month', '=', current_month),
                    ('year', '=', current_year),
                ])

                summary_data = {
                    'year': current_year,
                    'month': current_month,
                    'month_name': month_name,
                    'category': data['category'],
                    'license_plate': data['license_plate'],
                    'status': data['status'],
                    'type': data['type'],
                    'total': data['total'],
                    'formatted_date': custom_create_date,
                    'total_target_util': vehicle_target.target_days_utilization if vehicle_target else 0,
                }
                summary_data_list.append(summary_data)

            # Bulk insert ke summary table
            if summary_data_list:
                self.create(summary_data_list)
                _logger.info(
                    f'Successfully inserted {len(summary_data_list)} records to mart.vehicle.utilization.smry')

                # Log detail summary
                for data in summary_data_list:
                    _logger.info(
                        f'Summary: {data["license_plate"]} - {data["status"]} - {data["category"]} - {data["type"]} = {data["total"]} records')
            else:
                _logger.info('No summary data to insert')

            _logger.info('Job Insert Data Mart Summary completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart summary: %s') % str(e))

    def insert_data_mart_to_staging_and_summary(self):
        """
        Method gabungan untuk menjalankan insert data mart staging dan summary sekaligus
        """
        _logger.info('Job Insert Data Mart (Staging + Summary) is running')

        try:
            # Step 1: Insert data ke staging table
            mart_utilization = self.env['mart.vehicle.utilization']
            mart_utilization.insert_data_mart_to_staging_table()

            # Step 2: Insert data ke summary table
            self.insert_data_mart_summary()

            _logger.info('Job Insert Data Mart (Staging + Summary) completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_to_staging_and_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart staging dan summary: %s') % str(e))

class MartVehicleUtilizationWeeklySmry(models.Model):
    _name = 'mart.vehicle.utilization.weekly.smry'
    # _log_access = False

    year = fields.Integer()
    month = fields.Integer()
    week = fields.Integer()  # Field week
    category = fields.Char(string="TYPE")
    license_plate = fields.Char(string="NOPOL")
    status = fields.Char()
    total = fields.Integer(string="ACTUAL UTI. (Days)")
    type = fields.Char(string="PRODUCT")
    month_name = fields.Char()
    formatted_date = fields.Date()
    branch_project = fields.Char()

    def get_month_name_indonesian(self, month_number):
        """Fungsi untuk mengkonversi nomor bulan ke nama bulan dalam bahasa Indonesia"""
        month_names = {
            1: 'Januari',
            2: 'Februari',
            3: 'Maret',
            4: 'April',
            5: 'Mei',
            6: 'Juni',
            7: 'Juli',
            8: 'Agustus',
            9: 'September',
            10: 'Oktober',
            11: 'November',
            12: 'Desember'
        }
        return month_names.get(month_number, '')

    def get_week_number(self, day):
        """Fungsi untuk menghitung nomor minggu berdasarkan tanggal"""
        if day <= 7:
            return 1
        elif day <= 14:
            return 2
        elif day <= 21:
            return 3
        elif day <= 28:
            return 4
        else:
            return 5

    def get_target_utilization(self, status):
        """Fungsi untuk menentukan target utilization berdasarkan status"""
        target_mapping = {
            'UTILIZATION': 100,
            'READY FOR USE': 80,
            'BREAKDOWN': 0
        }
        return target_mapping.get(status, 50)

    def create_custom_date(self, year, month):
        """Fungsi untuk membuat datetime berdasarkan year + month + tanggal 1 + jam sekarang"""
        current_time = datetime.now()
        try:
            # Buat datetime dengan year dan month dari data, tanggal 1, dan jam sekarang
            custom_date = datetime(
                year=year,
                month=month,
                day=1,
                hour=current_time.hour,
                minute=current_time.minute,
                second=current_time.second,
                microsecond=current_time.microsecond
            )
            return custom_date
        except ValueError as e:
            _logger.error(f'Error creating custom date for year {year}, month {month}: {str(e)}')
            return datetime.now()

    def insert_data_mart_summary(self):
        """
        Insert data summary dari mart.vehicle.utilization ke mart.vehicle.utilization.weekly.smry
        dengan pengelompokan berdasarkan week dan status
        """
        _logger.info('Job Insert Data Mart Summary is running')

        try:
            # Mendapatkan tanggal hari ini
            today = datetime.now().date()
            current_year = today.year
            current_month = today.month
            month_name = self.get_month_name_indonesian(current_month)
            custom_create_date = self.create_custom_date(current_year, current_month)

            # Mendapatkan awal dan akhir bulan ini
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

            _logger.info(f'Processing summary for period: {start_of_month} to {end_of_month}')

            # Menghapus data summary untuk bulan ini
            summary_records_to_delete = self.search([
                ('year', '=', current_year),
                ('month', '=', current_month)
            ])

            if summary_records_to_delete:
                deleted_count = len(summary_records_to_delete)
                summary_records_to_delete.unlink()
                _logger.info(f'Deleted {deleted_count} summary records for {current_year}-{current_month:02d}')
            else:
                _logger.info(f'No summary records found to delete for {current_year}-{current_month:02d}')

            # Mengambil data dari mart.vehicle.utilization untuk bulan ini
            mart_records = self.env['mart.vehicle.utilization'].search([
                ('date', '>=', start_of_month),
                ('date', '<=', end_of_month)
            ])

            if len(self.search([])) <= 0:
                mart_records = self.env['mart.vehicle.utilization'].search([])

            if not mart_records:
                _logger.info('No mart records found for current month')
                return

            _logger.info(f'Found {len(mart_records)} mart records to process')

            # Grouping data berdasarkan kombinasi: year, month, week, category, license_plate, status, type, branch_project
            grouped_data = {}

            for record in mart_records:
                # Extract date components
                record_date = record.date
                record_year = record_date.year
                record_month = record_date.month
                record_day = record_date.day
                record_week = self.get_week_number(record_day)

                # Create key untuk grouping (tanpa day)
                key = (
                    record_year,
                    record_month,
                    record_week,
                    record.category or '',
                    record.license_plate or '',
                    record.status or '',
                    record.type or '',
                    record.branch_project or ''
                )

                if key not in grouped_data:
                    grouped_data[key] = {
                        'year': record_year,
                        'month': record_month,
                        'week': record_week,
                        'category': record.category,
                        'license_plate': record.license_plate,
                        'status': record.status,
                        'type': record.type,
                        'branch_project': record.branch_project,
                        'total': 0,
                        'formatted_date': record_date.strftime('%Y-%m-%d')
                    }

                # Increment total count
                grouped_data[key]['total'] += 1

            # Prepare data untuk insert ke summary table
            summary_data_list = []
            for key, data in grouped_data.items():
                # Get vehicle target
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', data['license_plate'])
                ], limit=1)

                if vehicle and data['license_plate']:
                    vehicle_target = self.env['vehicle.target.line'].search([
                        ('vehicle_id', '=', vehicle.id),
                        ('month', '=', data['month']),
                        ('year', '=', data['year']),
                    ]) if vehicle else None

                    # Get target utilization based on status
                    target_util = self.get_target_utilization(data['status'])
                    if vehicle_target and vehicle_target.target_days_utilization:
                        target_util = vehicle_target.target_days_utilization

                    # Use the latest formatted date
                    formatted_date = data['formatted_date']

                    summary_data = {
                        'year': data['year'],
                        'month': data['month'],
                        'week': data['week'],
                        'month_name': self.get_month_name_indonesian(data['month']),
                        'category': data['category'],
                        'license_plate': data['license_plate'],
                        'status': data['status'],
                        'type': data['type'],
                        'branch_project': data['branch_project'],
                        'total': data['total'],
                        'formatted_date': formatted_date,
                    }

                    if str(summary_data['status']).upper() == 'DRIVER NOT':
                        summary_data['status'] = 'DRIVER NOT READY'

                    summary_data_list.append(summary_data)

            # Bulk insert ke summary table
            if summary_data_list:
                self.create(summary_data_list)
                _logger.info(f'Successfully inserted {len(summary_data_list)} records to mart.vehicle.utilization.weekly.smry')

                # Log detail summary
                for data in summary_data_list:
                    _logger.info(f'Summary: Week {data["week"]} - {data["license_plate"]} - {data["status"]} - {data["category"]} - {data["type"]} - {data["branch_project"]} = {data["total"]} records')
            else:
                _logger.info('No summary data to insert')

            _logger.info('Job Insert Data Mart Summary completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart summary: %s') % str(e))

    def insert_data_mart_summary_sql(self):
        """
        Alternative method using SQL query for better performance
        """
        _logger.info('Job Insert Data Mart Summary (SQL) is running')

        try:
            # Get current month info
            today = datetime.now().date()
            current_year = today.year
            current_month = today.month

            # Delete existing records for current month
            delete_query = """
                DELETE FROM mart_vehicle_utilization_weekly_smry 
                WHERE year = %s AND month = %s
            """
            self.env.cr.execute(delete_query, (current_year, current_month))

            # SQL query to insert summary data with week calculation (tanpa day)
            insert_query = """
                INSERT INTO mart_vehicle_utilization_weekly_smry (
                    year, month, week, total, category, license_plate, 
                    status, type, branch_project, month_name, formatted_date,
                    create_date, write_date, create_uid, write_uid
                )
                WITH weekly_data AS (
                    SELECT 
                        EXTRACT(YEAR FROM date) as year,
                        EXTRACT(MONTH FROM date) as month,
                        CASE 
                            WHEN EXTRACT(DAY FROM date) BETWEEN 1 AND 7 THEN 1
                            WHEN EXTRACT(DAY FROM date) BETWEEN 8 AND 14 THEN 2
                            WHEN EXTRACT(DAY FROM date) BETWEEN 15 AND 21 THEN 3
                            WHEN EXTRACT(DAY FROM date) BETWEEN 22 AND 28 THEN 4
                            ELSE 5
                        END as week,
                        category,
                        license_plate,
                        status,
                        type,
                        branch_project,
                        CASE EXTRACT(MONTH FROM date)
                            WHEN 1 THEN 'Januari'
                            WHEN 2 THEN 'Februari'
                            WHEN 3 THEN 'Maret'
                            WHEN 4 THEN 'April'
                            WHEN 5 THEN 'Mei'
                            WHEN 6 THEN 'Juni'
                            WHEN 7 THEN 'Juli'
                            WHEN 8 THEN 'Agustus'
                            WHEN 9 THEN 'September'
                            WHEN 10 THEN 'Oktober'
                            WHEN 11 THEN 'November'
                            WHEN 12 THEN 'Desember'
                        END as month_name,
                        date
                    FROM mart_vehicle_utilization
                    WHERE EXTRACT(YEAR FROM date) = %s 
                      AND EXTRACT(MONTH FROM date) = %s
                      AND date IS NOT NULL
                )
                SELECT 
                    year,
                    month,
                    week,
                    COUNT(*) as total,
                    COALESCE(category, '') as category,
                    COALESCE(license_plate, '') as license_plate,
                    COALESCE(status, '') as status,
                    COALESCE(type, '') as type,
                    COALESCE(branch_project, '') as branch_project,
                    month_name,
                    CONCAT('Week ', week, ': ', MIN(TO_CHAR(date, 'YYYY-MM-DD')), ' - ', MAX(TO_CHAR(date, 'YYYY-MM-DD'))) as formatted_date,
                    NOW() as create_date,
                    NOW() as write_date,
                    %s as create_uid,
                    %s as write_uid
                FROM weekly_data
                GROUP BY 
                    year, month, week, category, license_plate, 
                    status, type, branch_project, month_name
                ORDER BY year, month, week
            """

            self.env.cr.execute(insert_query, (
                current_year, current_month,
                self.env.user.id, self.env.user.id
            ))

            # Get count of inserted records
            count_query = """
                SELECT COUNT(*) FROM mart_vehicle_utilization_weekly_smry 
                WHERE year = %s AND month = %s
            """
            self.env.cr.execute(count_query, (current_year, current_month))
            inserted_count = self.env.cr.fetchone()[0]

            _logger.info(f'Successfully inserted {inserted_count} records using SQL method')

            # Log sample data untuk debugging
            sample_query = """
                SELECT week, status, license_plate, total 
                FROM mart_vehicle_utilization_weekly_smry 
                WHERE year = %s AND month = %s
                ORDER BY week, status, license_plate
                LIMIT 10
            """
            self.env.cr.execute(sample_query, (current_year, current_month))
            sample_data = self.env.cr.fetchall()

            _logger.info('Sample inserted data:')
            for row in sample_data:
                _logger.info(f'Week {row[0]}, Status: {row[1]}, License: {row[2]}, Total: {row[3]}')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_summary_sql: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart summary SQL: %s') % str(e))

    def insert_data_mart_to_staging_and_summary(self):
        """
        Method gabungan untuk menjalankan insert data mart staging dan summary sekaligus
        """
        _logger.info('Job Insert Data Mart (Staging + Summary) is running')

        try:
            # Step 1: Insert data ke staging table
            mart_utilization = self.env['mart.vehicle.utilization']
            mart_utilization.insert_data_mart_to_staging_table()

            # Step 2: Insert data ke summary table
            # Pilih salah satu method: Python atau SQL
            # self.insert_data_mart_summary()  # Python method
            self.insert_data_mart_summary_sql()  # SQL method (recommended for performance)

            _logger.info('Job Insert Data Mart (Staging + Summary) completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_to_staging_and_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart staging dan summary: %s') % str(e))

class MartVehicleUtilizationDailySmry(models.Model):
    _name = 'mart.vehicle.utilization.daily.smry'
    # _log_access = False
    # Header Information
    category = fields.Char(string="TYPE", required=True, index=True)
    license_plate = fields.Char(string='NOPOL', required=True, index=True)
    formatted_date = fields.Date(string='Date', required=True, index=True)
    target_utilization = fields.Integer(string='TARGET UTI. (Days)', required=True)

    month = fields.Char(string='Month', required=True)
    month_name = fields.Char(string='Month', required=True)
    year = fields.Integer(string='Year', required=True)

    day_1 = fields.Char(string='1')
    day_2 = fields.Char(string='2')
    day_3 = fields.Char(string='3')
    day_4 = fields.Char(string='4')
    day_5 = fields.Char(string='5')
    day_6 = fields.Char(string='6')
    day_7 = fields.Char(string='7')
    day_8 = fields.Char(string='8')
    day_9 = fields.Char(string='9')
    day_10 = fields.Char(string='10')
    day_11 = fields.Char(string='11')
    day_12 = fields.Char(string='12')
    day_13 = fields.Char(string='13')
    day_14 = fields.Char(string='14')
    day_15 = fields.Char(string='15')
    day_16 = fields.Char(string='16')
    day_17 = fields.Char(string='17')
    day_18 = fields.Char(string='18')
    day_19 = fields.Char(string='19')
    day_20 = fields.Char(string='20')
    day_21 = fields.Char(string='21')
    day_22 = fields.Char(string='22')
    day_23 = fields.Char(string='23')
    day_24 = fields.Char(string='24')
    day_25 = fields.Char(string='25')
    day_26 = fields.Char(string='26')
    day_27 = fields.Char(string='27')
    day_28 = fields.Char(string='28')
    day_29 = fields.Char(string='29')
    day_30 = fields.Char(string='30')
    day_31 = fields.Char(string='31')

    total_ready_for_use = fields.Integer(string='Total Actual Ready For Use')
    total_utilization = fields.Integer(string='Total Actual Utilization')
    total_breakdown = fields.Integer(string='Total Actual Breakdown')
    total_driver_not_ready = fields.Integer(string='Total Actual Driver Not Ready')
    percentage_ready_for_use = fields.Float(string='Percentage Ready For Use')
    percentage_utilization = fields.Float(string='Percentage Utilization')
    percentage_breakdown = fields.Float(string='Percentage Breakdown')
    percentage_driver_not_ready = fields.Float(string='Percentage Driver Not Ready')

    def get_month_name_indonesian(self, month_number):
        """Fungsi untuk mengkonversi nomor bulan ke nama bulan dalam bahasa Indonesia"""
        month_names = {
            1: 'Januari',
            2: 'Februari',
            3: 'Maret',
            4: 'April',
            5: 'Mei',
            6: 'Juni',
            7: 'Juli',
            8: 'Agustus',
            9: 'September',
            10: 'Oktober',
            11: 'November',
            12: 'Desember'
        }
        return month_names.get(month_number, '')

    def get_week_number(self, day):
        """Fungsi untuk menghitung nomor minggu berdasarkan tanggal"""
        if day <= 7:
            return 1
        elif day <= 14:
            return 2
        elif day <= 21:
            return 3
        elif day <= 28:
            return 4
        else:
            return 5

    def calculate_monthly_totals(self, daily_status_data, days_in_month):
        """
        Fungsi untuk menghitung total bulanan berdasarkan status harian
        """
        totals = {
            'total_ready_for_use': 0,
            'total_utilization': 0,
            'total_breakdown': 0,
            'total_driver_not_ready': 0
        }

        for day in range(1, days_in_month + 1):
            status = daily_status_data.get(day, 'READY FOR USE')
            # if not status or status == '':
            #     status = 'READY FOR USE'

            status_upper = str(status).upper()

            # Normalisasi status - handle berbagai variasi status
            if status_upper in ['DRIVER NOT', 'DRIVER NOT READY']:
                status_upper = 'DRIVER NOT READY'
            elif status_upper in ['LICENSE NOT', 'LICENSE NOT READY']:
                status_upper = 'DRIVER NOT READY'  # Anggap sebagai driver not ready
            elif status_upper in ['BREAKDOWN', 'MAINTENANCE']:
                status_upper = 'BREAKDOWN'
            elif status_upper in ['UTILIZATION', 'USED']:
                status_upper = 'UTILIZATION'
            elif status_upper in ['READY FOR USE', 'AVAILABLE', 'READY']:
                status_upper = 'READY FOR USE'

            # Hitung berdasarkan status yang sudah dinormalisasi
            if status_upper == 'READY FOR USE':
                totals['total_ready_for_use'] += 1
            elif status_upper == 'UTILIZATION':
                totals['total_utilization'] += 1
            elif status_upper == 'BREAKDOWN':
                totals['total_breakdown'] += 1
            elif status_upper == 'DRIVER NOT READY':
                totals['total_driver_not_ready'] += 1

        return totals

    def insert_data_mart_daily_summary(self, year=None, month=None):
        """
        Insert data summary dari mart.vehicle.utilization ke mart.vehicle.utilization.daily.smry
        dengan pengelompokan berdasarkan harian dan status

        Args:
            year: Tahun yang ingin diproses (default: tahun saat ini)
            month: Bulan yang ingin diproses (default: bulan saat ini)
        """
        _logger.info('Job Insert Data Mart Daily Summary is running')

        try:
            # Jika tidak ada parameter, ambil semua bulan yang ada di data
            if year is None and month is None:
                # Ambil semua kombinasi year-month yang ada di data
                mart_records = self.env['mart.vehicle.utilization'].search([])
                if not mart_records:
                    _logger.info('No mart records found')
                    return

                # Dapatkan unique year-month combinations
                year_month_combinations = set()
                for record in mart_records:
                    year_month_combinations.add((record.date.year, record.date.month))

                # Process each year-month combination
                for year_val, month_val in sorted(year_month_combinations):
                    self._process_monthly_summary(year_val, month_val)

                _logger.info('Job Insert Data Mart Daily Summary completed successfully for all months')
                return

            # Jika ada parameter, proses bulan/tahun tertentu
            if year is None:
                year = datetime.now().year
            if month is None:
                month = datetime.now().month

            self._process_monthly_summary(year, month)
            _logger.info(f'Job Insert Data Mart Daily Summary completed successfully for {year}-{month:02d}')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_daily_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart daily summary: %s') % str(e))

    def _process_monthly_summary(self, year, month):
        """
        Process daily summary untuk bulan tertentu
        """
        month_name = self.get_month_name_indonesian(month)

        # Mendapatkan awal dan akhir bulan
        start_of_month = datetime(year, month, 1).date()
        if month == 12:
            end_of_month = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_of_month = datetime(year, month + 1, 1).date() - timedelta(days=1)

        _logger.info(f'Processing daily summary for period: {start_of_month} to {end_of_month}')

        # Menghapus data summary untuk bulan ini
        summary_records_to_delete = self.search([
            ('year', '=', year),
            ('month', '=', str(month).zfill(2))
        ])

        if summary_records_to_delete:
            deleted_count = len(summary_records_to_delete)
            summary_records_to_delete.unlink()
            _logger.info(f'Deleted {deleted_count} daily summary records for {year}-{month:02d}')
        else:
            _logger.info(f'No daily summary records found to delete for {year}-{month:02d}')

        # Mengambil data dari mart.vehicle.utilization untuk bulan ini
        mart_records = self.env['mart.vehicle.utilization'].search([
            ('date', '>=', start_of_month),
            ('date', '<=', end_of_month)
        ])

        if not mart_records:
            _logger.info(f'No mart records found for {year}-{month:02d}')
            return

        _logger.info(f'Found {len(mart_records)} mart records to process for {year}-{month:02d}')

        # Grouping data berdasarkan kombinasi: year, month, license_plate (tanpa category untuk menghindari duplikasi)
        grouped_data = {}

        for record in mart_records:
            # Extract date components
            record_date = record.date
            record_year = record_date.year
            record_month = record_date.month

            # Skip records yang license_plate kosong
            if not record.license_plate:
                continue

            # Create key untuk grouping berdasarkan license_plate saja (tanpa category)
            key = (
                record_year,
                record_month,
                record.license_plate or ''
            )

            if key not in grouped_data:
                # Ambil category dari record pertama yang ditemukan, atau cari dari fleet.vehicle
                category = record.category or ''
                if not category:
                    # Cari category dari fleet.vehicle jika tidak ada di record
                    vehicle = self.env['fleet.vehicle'].search([
                        ('license_plate', '=', record.license_plate)
                    ], limit=1)
                    if vehicle and vehicle.category_id:
                        category = vehicle.category_id.name

                grouped_data[key] = {
                    'year': record_year,
                    'month': record_month,
                    'month_name': month_name,
                    'category': category,
                    'license_plate': record.license_plate,
                    'daily_status': {},  # Dictionary untuk menyimpan status per hari
                    'formatted_date': start_of_month  # Tanggal awal bulan
                }
            else:
                # Update category jika record sebelumnya tidak memiliki category
                if not grouped_data[key]['category'] and record.category:
                    grouped_data[key]['category'] = record.category

            # Set status untuk hari tersebut
            day_number = record_date.day
            grouped_data[key]['daily_status'][day_number] = record.status or ''

        # Prepare data untuk insert ke summary table
        summary_data_list = []
        for key, data in grouped_data.items():
            # Get vehicle target
            vehicle = self.env['fleet.vehicle'].search([
                ('license_plate', '=', data['license_plate'])
            ], limit=1)

            vehicle_target = None
            if vehicle:
                vehicle_target = self.env['vehicle.target.line'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('month', '=', int(data['month'])),
                    ('year', '=', data['year']),
                ], limit=1)

            # Get target utilization (default)
            target_util = 0
            if vehicle_target and vehicle_target.target_days_utilization:
                target_util = vehicle_target.target_days_utilization

            # Get days in month
            days_in_month = calendar.monthrange(data['year'], data['month'])[1]

            # Calculate monthly totals
            monthly_totals = self.calculate_monthly_totals(data['daily_status'], days_in_month)

            # Prepare summary data
            summary_data = {
                'year': data['year'],
                'month': str(data['month']).zfill(2),
                'month_name': data['month_name'],
                'category': data['category'] or '',
                'license_plate': data['license_plate'],
                'target_utilization': target_util,
                'formatted_date': data['formatted_date'],
                'total_ready_for_use': monthly_totals['total_ready_for_use'],
                'total_utilization': monthly_totals['total_utilization'],
                'total_breakdown': monthly_totals['total_breakdown'],
                'total_driver_not_ready': monthly_totals['total_driver_not_ready'],
                'percentage_ready_for_use': round(monthly_totals['total_ready_for_use'] / target_util * 100, 1) if target_util > 0 else 0,
                'percentage_utilization': round(monthly_totals['total_utilization'] / target_util * 100, 1) if target_util > 0 else 0,
                'percentage_breakdown': round(monthly_totals['total_breakdown'] / target_util * 100, 1) if target_util > 0 else 0,
                'percentage_driver_not_ready': round(monthly_totals['total_driver_not_ready'] / target_util * 100, 1) if target_util > 0 else 0,
            }

            # Set status untuk setiap hari dalam bulan
            for day in range(1, 32):  # day_1 sampai day_31
                day_field = f'day_{day}'
                if day <= days_in_month:
                    # Ambil status dari daily_status atau set default
                    status = data['daily_status'].get(day, 'READY FOR USE')
                    if not status or status == '':
                        status = 'READY FOR USE'

                    status_to_upper = str(status).upper()

                    # Normalisasi status untuk display
                    if status_to_upper in ['DRIVER NOT', 'DRIVER NOT READY']:
                        status = 'DRIVER NOT READY'
                    elif status_to_upper in ['LICENSE NOT', 'LICENSE NOT READY']:
                        status = 'DRIVER NOT READY'
                    elif status_to_upper in ['BREAKDOWN', 'MAINTENANCE']:
                        status = 'BREAKDOWN'
                    elif status_to_upper in ['UTILIZATION', 'USED']:
                        status = 'UTILIZATION'
                    elif status_to_upper in ['READY FOR USE', 'AVAILABLE', 'READY']:
                        status = 'READY FOR USE'

                    summary_data[day_field] = status
                else:
                    # Hari tidak valid dalam bulan tersebut
                    summary_data[day_field] = ''

            summary_data_list.append(summary_data)

        # Bulk insert ke summary table
        if summary_data_list:
            self.create(summary_data_list)
            _logger.info(
                f'Successfully inserted {len(summary_data_list)} records to mart.vehicle.utilization.daily.smry for {year}-{month:02d}')

            # Log detail summary
            for data in summary_data_list:
                _logger.info(
                    f'Daily Summary: {data["license_plate"]} - {data["category"]} - Month: {data["month_name"]} {data["year"]} - '
                    f'Ready: {data["total_ready_for_use"]}, Utilization: {data["total_utilization"]}, '
                    f'Breakdown: {data["total_breakdown"]}, Driver Not Ready: {data["total_driver_not_ready"]}')
        else:
            _logger.info(f'No daily summary data to insert for {year}-{month:02d}')

    def process_all_months_summary(self):
        """
        Method untuk memproses summary semua bulan yang ada di data mart.vehicle.utilization
        """
        return self.insert_data_mart_daily_summary()

    def process_specific_month_summary(self, year, month):
        """
        Method untuk memproses summary bulan tertentu

        Args:
            year: Tahun (int)
            month: Bulan (int, 1-12)
        """
        return self.insert_data_mart_daily_summary(year, month)
        """
        Helper method untuk mendapatkan target utilization berdasarkan status
        """
        # Mapping status ke target utilization
        status_mapping = {
            'UTILIZATION': 'UTILIZATION',
            'AVAILABLE': 'AVAILABLE',
            'MAINTENANCE': 'MAINTENANCE',
            'USED': 'USED',
        }
        return status_mapping.get(status, 'UTILIZATION')

    def create_custom_date(self, year, month):
        """
        Helper method untuk membuat custom date format
        """
        try:
            return datetime(year, month, 1).date()
        except ValueError:
            return datetime.now().date()

    def cleanup_old_daily_summary(self, months_to_keep=6):
        """
        Method untuk membersihkan data summary lama
        Args:
            months_to_keep: Jumlah bulan yang akan dipertahankan (default: 6)
        """
        _logger.info('Job Cleanup Old Daily Summary is running')

        try:
            # Hitung tanggal cutoff
            today = datetime.now().date()
            cutoff_date = today - timedelta(days=months_to_keep * 30)

            # Cari records yang akan dihapus
            old_records = self.search([
                ('formatted_date', '<', cutoff_date)
            ])

            if old_records:
                deleted_count = len(old_records)
                old_records.unlink()
                _logger.info(f'Deleted {deleted_count} old daily summary records older than {cutoff_date}')
            else:
                _logger.info('No old daily summary records found to delete')

        except Exception as e:
            _logger.error(f'Error in cleanup_old_daily_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat membersihkan data summary lama: %s') % str(e))

    def get_daily_utilization_stats(self, year, month):
        """
        Method untuk mendapatkan statistik utilization harian
        """
        records = self.search([
            ('year', '=', year),
            ('month', '=', str(month).zfill(2))
        ])

        stats = {
            'total_vehicles': len(records),
            'categories': {},
            'daily_usage': {}
        }

        days_in_month = calendar.monthrange(year, month)[1]

        for record in records:
            # Count by category
            category = record.category or 'Unknown'
            if category not in stats['categories']:
                stats['categories'][category] = 0
            stats['categories'][category] += 1

            # Count daily usage
            for day in range(1, days_in_month + 1):
                day_field = f'day_{day}'
                status = getattr(record, day_field, '')

                if status and status != 'AVAILABLE':
                    if day not in stats['daily_usage']:
                        stats['daily_usage'][day] = 0
                    stats['daily_usage'][day] += 1

        return stats

class MartVehicleUtilizationMonthlySmry(models.Model):
    _name = 'mart.vehicle.utilization.monthly.smry'
    # _log_access = False

    year = fields.Integer()
    month = fields.Integer()
    category = fields.Char(string="TYPE")
    license_plate = fields.Char(string="NOPOL")
    status = fields.Char()
    total = fields.Integer(string="ACTUAL UTI. (Days)")
    type = fields.Char(string="PRODUCT")
    month_name = fields.Char()
    formatted_date = fields.Datetime(string="Formatted Date")
    total_target_util = fields.Integer(string="Target Utilize")
    # achieve_unit_util = fields.Char()

    def get_month_name_indonesian(self, month_number):
        """Fungsi untuk mengkonversi nomor bulan ke nama bulan dalam bahasa Indonesia"""
        month_names = {
            1: 'Januari',
            2: 'Februari',
            3: 'Maret',
            4: 'April',
            5: 'Mei',
            6: 'Juni',
            7: 'Juli',
            8: 'Agustus',
            9: 'September',
            10: 'Oktober',
            11: 'November',
            12: 'Desember'
        }
        return month_names.get(month_number, '')

    def create_custom_date(self, year, month):
        """Fungsi untuk membuat datetime berdasarkan year + month + tanggal 1 + jam sekarang"""
        current_time = datetime.now()
        try:
            # Buat datetime dengan year dan month dari data, tanggal 1, dan jam sekarang
            custom_date = datetime(
                year=year,
                month=month,
                day=1,
                hour=current_time.hour,
                minute=current_time.minute,
                second=current_time.second,
                microsecond=current_time.microsecond
            )
            return custom_date
        except ValueError as e:
            _logger.error(f'Error creating custom date for year {year}, month {month}: {str(e)}')
            return datetime.now()

    def insert_data_mart_summary(self):
        _logger.info('Job Insert Data Mart Monthly Summary is running')

        try:
            # Mendapatkan tanggal hari ini untuk filter bulan/tahun saat ini
            today = datetime.now().date()
            current_year = today.year
            current_month = today.month

            _logger.info(f'Processing summary for {current_year}-{current_month:02d}')

            # Hapus data summary yang sudah ada untuk bulan/tahun saat ini
            # untuk mencegah duplikat saat re-run
            existing_records = self.search([
                ('year', '=', current_year),
                ('month', '=', current_month)
            ])

            if existing_records:
                deleted_count = len(existing_records)
                existing_records.unlink()
                _logger.info(f'Deleted {deleted_count} existing summary records for {current_year}-{current_month:02d}')

            # Query yang diperbaiki untuk menghindari duplikat dan perhitungan yang benar
            # Step 1: Deduplikasi data sumber terlebih dahulu, lalu hitung READY FOR USE
            query = """
            WITH deduplicated_data AS (
                -- Deduplikasi data sumber berdasarkan license_plate, status, year, month
                -- Ambil yang category-nya tidak kosong, atau yang total terbesar jika sama-sama kosong/tidak kosong
                SELECT DISTINCT ON (license_plate, status, year, month)
                    year,
                    month,
                    total,
                    COALESCE(NULLIF(category, ''), 'UNKNOWN') as category,
                    license_plate,
                    status
                FROM mart_vehicle_utilization_smry
                WHERE status IN ('UTILIZATION', 'BREAKDOWN', 'DRIVER NOT', 'LICENSE NOT')
                    AND year = %(current_year)s 
                    AND month = %(current_month)s
                ORDER BY license_plate, status, year, month, 
                         CASE WHEN category IS NOT NULL AND category != '' THEN 1 ELSE 2 END,
                         total DESC
            ),
            aggregated_usage AS (
                -- Agregasi per vehicle untuk menghitung total hari terpakai
                SELECT 
                    year,
                    month,
                    license_plate,
                    category,
                    SUM(total) as total_used_days
                FROM deduplicated_data
                GROUP BY year, month, license_plate, category
            )
            SELECT * FROM (
                -- Ambil data utilization, breakdown, driver not ready yang sudah deduplikasi
                SELECT 
                    year, 
                    month, 
                    total, 
                    category, 
                    license_plate, 
                    status
                FROM deduplicated_data

                UNION ALL

                -- Perhitungan READY FOR USE yang benar
                SELECT 
                    au.year,
                    au.month,
                    EXTRACT(
                        DAY FROM (DATE_TRUNC('month', TO_DATE(au.year::text || '-' || LPAD(au.month::text, 2, '0') || '-01', 'YYYY-MM-DD')) 
                                  + INTERVAL '1 month - 1 day')
                    )::int - au.total_used_days AS total,
                    au.category,
                    au.license_plate,
                    'READY FOR USE' AS status
                FROM aggregated_usage au
                WHERE EXTRACT(
                    DAY FROM (DATE_TRUNC('month', TO_DATE(au.year::text || '-' || LPAD(au.month::text, 2, '0') || '-01', 'YYYY-MM-DD')) 
                              + INTERVAL '1 month - 1 day')
                )::int - au.total_used_days > 0
            ) final_result
            ORDER BY final_result.year, final_result.license_plate, final_result.month, final_result.status ASC
            """

            # Execute query dengan parameter untuk menghindari SQL injection
            self.env.cr.execute(query, {
                'current_year': current_year,
                'current_month': current_month
            })
            query_results = self.env.cr.fetchall()

            # Mendapatkan nama kolom
            column_names = [desc[0] for desc in self.env.cr.description]

            _logger.info(f'Query executed successfully. Retrieved {len(query_results)} rows')
            _logger.info(f'Column names: {column_names}')

            # Tidak perlu lagi deduplication di Python karena sudah dilakukan di SQL
            _logger.info(f'After SQL deduplication: {len(query_results)} records')

            # Prepare data untuk bulk insert - langsung tanpa deduplication lagi
            records_to_create = []

            for row in query_results:
                # Konversi row menjadi dictionary untuk kemudahan akses
                row_dict = dict(zip(column_names, row))
                # Cari vehicle dan target
                vehicle = self.env['fleet.vehicle'].search([
                    ('license_plate', '=', row_dict['license_plate']),
                ], limit=1)

                vehicle_target = self.env['vehicle.target.line'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('month', '=', row_dict['month']),
                    ('year', '=', row_dict['year']),
                ], limit=1)

                # Generate month_name dan create_date
                month_name = self.get_month_name_indonesian(row_dict['month'])
                custom_create_date = self.create_custom_date(row_dict['year'], row_dict['month'])

                # Prepare record data
                record_data = {
                    'year': row_dict['year'],
                    'month': row_dict['month'],
                    'category': row_dict['category'] or '',  # Handle None values
                    'license_plate': row_dict['license_plate'],
                    'status': row_dict['status'],
                    'total': row_dict['total'],
                    'month_name': month_name,
                    'formatted_date': custom_create_date,
                    'total_target_util': vehicle_target.target_days_utilization if vehicle_target else 0,
                }

                if str(record_data['status']).upper() == 'DRIVER NOT':
                    record_data['status'] = 'DRIVER NOT READY'

                records_to_create.append(record_data)

            # Bulk create records
            if records_to_create:
                created_records = self.create(records_to_create)
                _logger.info(f'Successfully created {len(created_records)} summary records')

                # Log detail untuk debugging
                for record_data in records_to_create:
                    _logger.info(
                        f'Created: {record_data["license_plate"]} - {record_data["status"]} - '
                        f'{record_data["category"]} = {record_data["total"]} days'
                    )
            else:
                _logger.info('No records to create')

            _logger.info('Job Insert Data Mart Monthly Summary completed successfully')

        except Exception as e:
            _logger.error(f'Error in insert_data_mart_summary: {str(e)}')
            raise UserError(_('Terjadi kesalahan saat memproses data mart summary: %s') % str(e))

