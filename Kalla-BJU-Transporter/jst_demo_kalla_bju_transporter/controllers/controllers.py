import json
import requests
from datetime import datetime, date
from odoo import http, fields
from odoo.http import content_disposition, request, Response
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape
from collections import defaultdict
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class XLSXReportController(http.Controller):
    """XlsxReport generating controller"""

    @http.route('/xlsx_reports', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report_xlsx(self, model, options, output_format, **kw):
        """
        Generate an XLSX report based on the provided data and return it as a
        response.
        """
        uid = request.session.uid
        report_obj = request.env[model].with_user(uid)
        options = json.loads(options)
        mcm = request.env[model].search([('id', '=', options['model_id'])])
        date = mcm.date.strftime('%b %y')
        token = 'dummy-because-api-expects-one'
        # pekerjaan = po.pekerjaan_id.name or ""
        # project = po.project_id.name or ""
        # tahun_anggaran = po.tahun_anggaran or ""
        report_name = 'Gaji Driver ' + date + '.xlsx'
        token = 'dummy-because-api-expects-one'
        try:
            if output_format == 'csv':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', 'text/csv; charset=utf-8'),
                        ('Content-Disposition', content_disposition(report_name)),
                    ]
                )
                # tulis CSV ke response
                report_obj.get_csv_report(options, response)
                response.set_cookie('fileToken', token)
                return response
                
                
            if output_format == 'xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', 'application/vnd.ms-excel'),
                        ('Content-Disposition',
                         content_disposition(report_name))
                    ]
                )
                report_obj.get_xlsx_report(options, response)
                response.set_cookie('fileToken', token)
                return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))

class McmDriverController(http.Controller):

    @http.route('/mcm_driver/report/xlsx', type='http', auth='user')
    def generate_mcm_driver_report(self, wizard_id=None, **kwargs):
        if not wizard_id:
            return request.not_found()

        wizard = request.env['mcm.driver'].sudo().browse(int(wizard_id))
        if not wizard.exists():
            return request.not_found()

        # Create response object
        response = request.make_response(
            None,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="MCM_Driver_Report.xlsx"')
            ]
        )

        # Call your original report generator
        wizard.get_xlsx_report({'model_id': wizard.id}, response)

        return response
    
    @http.route('/mcm_driver/report/csv', type='http', auth='user')
    def mcm_driver_report_csv(self, wizard_id=None, **kw):
        wizard = request.env['mcm.driver'].browse(int(wizard_id or 0))
        if not wizard.exists():
            return request.not_found()

        date = wizard.date or fields.Date.today()
        report_name = f"Gaji Driver {date.strftime('%b %y')}.csv"
        token = 'dummy-because-api-expects-one'

        response = request.make_response(
            None,
            headers=[
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', content_disposition(report_name)),
            ]
        )
        wizard.get_csv_report(response)
        response.set_cookie('fileToken', token)
        return response
    
    @http.route('/mcm_driver/report/csv_zip', type='http', auth='user')
    def mcm_driver_report_csv_zip(self, wizard_id=None, **kw):
        wiz = request.env['mcm.driver'].browse(int(wizard_id or 0))
        if not wiz.exists():
            return request.not_found()

        date = wiz.date or fields.Date.today()
        filename = f"Gaji Driver {date.strftime('%b %y')}.zip"
        resp = request.make_response(
            None,
            headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', content_disposition(filename)),
            ]
        )
        wiz.get_csv_zip_report(resp)
        resp.set_cookie('fileToken', 'ok')
        return resp

class MyAPIController(http.Controller):

    @http.route('/my_api/get_data', type='http', auth='public', methods=['GET'])
    def get_data(self):
        """Returns a list of records from a model"""
        records = request.env['fleet.vehicle'].sudo().search([])
        data = [{"id": rec.id, "name": rec.name} for rec in records]

        # Convert the list to JSON response
        return request.make_response(json.dumps(data))

    @http.route('/my_api/check', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_data(self, id, driver_c):
        """Returns a list of records from a model"""
        records = request.env['fleet.vehicle'].sudo().browse([int(id)])
        value = True if driver_c else False
        test = {'driver_confirmation': value, 'plan_armada_confirmation': value}
        records.sudo().write(test)

        # Convert the list to JSON response
        return request.make_response(json.dumps(test))

    @http.route('/api/kalla/report/checkpoint', type='http', auth='public', methods=['POST'], csrf=False)
    def fetch_last_checkpoint_data(self):
        """
        Controller untuk melakukan fetch data dari API eksternal
        Dapat diakses melalui: /api/kalla/report/checkpoint
        """
        try:
            client_headers = request.httprequest.headers
            # URL API eksternal yang akan diakses
            params = {
                # 'start_time': datetime.now().strftime("%Y-%m-%d 00:00:01"),
                # 'stop_time': datetime.now().strftime("%Y-%m-%d 23:59:59"),
                'start_time': f"{date.today()} 00:00:00",
                'stop_time': f"{date.today()} 23:59:59",
                'nopol': "",
                'event': "",
            }
            api_url = "https://vtsapi.easygo-gps.co.id/api/kalla/report/checkpoint"

            # Melakukan request ke API eksternal
            response = requests.post(api_url, headers=dict(client_headers), json=params)

            # Cek status response
            if response.status_code == 200:
                # Data berhasil diambil
                external_data = response.json()

                # Contoh pengolahan data jika diperlukan
                # Misalnya menyimpan ke model Odoo
                # self._process_external_data(external_data)

                # Return data ke client
                return Response(
                    json.dumps({
                        'success': True,
                        'data': external_data.get('Data', [])
                    }),
                    content_type='application/json'
                )
            else:
                # Handle error
                return Response(
                    json.dumps({
                        'success': False,
                        'error': f"Failed to fetch data: {response.status_code} - {response.text}"
                    }),
                    content_type='application/json'
                )

        except Exception as e:
            _logger.error("Error fetching external API: %s", str(e))
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json'
            )

    @http.route('/api/dummy/post/do', type='http', auth='public', methods=['POST'], csrf=False)
    def fetch_last_checkpoint_data(self):
        try:
            data = request.httprequest.get_data()
            params = json.loads(data) if data else {}
            
            if not data:
                return Response(
                    json.dumps({
                        'success': False,
                        'error': 'No data provided in the request body'
                    }),
                    content_type='application/json',
                    status=400
                )
            
            return Response(
                json.dumps({
                    'success': True,
                    'data': params,
                }),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            _logger.error("Error fetching external API: %s", str(e))
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json',
                status=500
            )

    @http.route('/my_api/report/checkpoint', type='http', auth='user', methods=['POST'], csrf=False)
    def store_last_checkpoint_data(self):
        """Returns a list of records from a model"""
        records = request.env['fleet.vehicle'].sudo().browse([int(id)])

        # Convert the list to JSON response
        return request.make_response(json.dumps({'test': 'ok'}))

    @http.route('/api/kalla/master/route', type='http', auth='public', methods=['POST'], csrf=False)
    def fetch_master_route_data(self):
        """
        Controller untuk melakukan fetch data dari API eksternal
        Dapat diakses melalui: /api/kalla/master/route
        """
        try:
            client_headers = request.httprequest.headers
            # URL API eksternal yang akan diakses
            params = {
                'search_param': "",
                'page': 0,
                'limit': 0,
            }
            api_url = "https://vtsapi.easygo-gps.co.id/api/Route/masterdata"

            # Melakukan request ke API eksternal
            response = requests.post(api_url, headers=dict(client_headers), json=params)

            # Cek status response
            if response.status_code == 200:
                # Data berhasil diambil
                external_data = response.json()

                # Return data ke client
                return Response(
                    json.dumps({
                        'success': True,
                        'data': external_data.get('Data', [])
                    }),
                    content_type='application/json'
                )
            else:
                # Handle error
                return Response(
                    json.dumps({
                        'success': False,
                        'error': f"Failed to fetch data: {response.status_code} - {response.text}"
                    }),
                    content_type='application/json'
                )

        except Exception as e:
            _logger.error("Error fetching external API: %s", str(e))
            return Response(
                json.dumps({
                    'success': False,
                    'error': str(e)
                }),
                content_type='application/json'
            )

class VehicleDashboardController(http.Controller):
    @http.route('/vehicle_dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, start_date=None, end_date=None):
        domain = []
        if start_date:
            domain.append(('date', '>=', start_date))
        if end_date:
            domain.append(('date', '<=', end_date))

        total_dos = request.env['fleet.do'].search_count(domain)
        pending_dos = request.env['fleet.do'].search_count([('state', '=', 'draft')])
        done_dos = request.env['fleet.do'].search_count([('state', '=', 'done'), ('status_do', '=', 'DO Match')])
        unmatch_dos = request.env['fleet.do'].search_count([('state', '=', 'draft'), ('status_do', '=', 'DO Unmatch')])
        match_dos = request.env['fleet.do'].search_count([('status_do', '=', 'DO Match'), ('status_document_status', 'in', ('Draft', 'draft'))])
        line_not_created_dos = request.env['fleet.do'].search_count(
            [('state', '=', 'draft'), ('status_do', '=', 'DO Line not Created')])
        trans_vehicle_count_ready = request.env['fleet.vehicle'].search_count([('vehicle_status', '=', 'ready'),
                                                                               (
                                                                               'last_status_description_id.name_description',
                                                                               '=', 'Ready for Use'),
                                                                               ('product_category_id.name', '=',
                                                                                'Transporter')])
        trans_vehicle_count_ready_on_book = request.env['fleet.vehicle'].search_count([('vehicle_status', '=', 'ready'),
                                                                                       (
                                                                                       'last_status_description_id.name_description',
                                                                                       '=', 'On Book'),
                                                                                       ('product_category_id.name', '=',
                                                                                        'Transporter')])
        trans_vehicle_count_on_going = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_going'), ('product_category_id.name', '=', 'Transporter')])
        trans_vehicle_count_on_return = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_return'), ('product_category_id.name', '=', 'Transporter')])
        trans_vehicle_count_not_ready = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'not_ready'), ('product_category_id.name', '=', 'Transporter')])
        vli_vehicle_count_ready = request.env['fleet.vehicle'].search_count([('vehicle_status', '=', 'ready'),
                                                                             (
                                                                             'last_status_description_id.name_description',
                                                                             '=', 'Ready for Use'),
                                                                             ('product_category_id.name', '=', 'VLI')])
        vli_vehicle_count_ready_on_book = request.env['fleet.vehicle'].search_count([('vehicle_status', '=', 'ready'),
                                                                                     (
                                                                                     'last_status_description_id.name_description',
                                                                                     '=', 'On Book'),
                                                                                     ('product_category_id.name', '=',
                                                                                      'VLI')])
        vli_vehicle_count_on_going = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_going'), ('product_category_id.name', '=', 'VLI')])
        vli_vehicle_count_on_return = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_return'), ('product_category_id.name', '=', 'VLI')])
        vli_vehicle_count_not_ready = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'not_ready'), ('product_category_id.name', '=', 'VLI')])
        truck_vehicle_count_ready = request.env['fleet.vehicle'].search_count([('vehicle_status', '=', 'ready'),
                                                                               (
                                                                               'last_status_description_id.name_description',
                                                                               '=', 'Ready for Use'),
                                                                               ('product_category_id.name', '=',
                                                                                'Trucking')])
        truck_vehicle_count_ready_on_book = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'ready'), ('last_status_description_id.name_description', '=', 'On Book')
                , ('product_category_id.name', '=', 'Trucking')])
        truck_vehicle_count_on_going = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_going'), ('product_category_id.name', '=', 'Trucking')])
        truck_vehicle_count_on_return = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'on_return'), ('product_category_id.name', '=', 'Trucking')])
        truck_vehicle_count_not_ready = request.env['fleet.vehicle'].search_count(
            [('vehicle_status', '=', 'not_ready'), ('product_category_id.name', '=', 'Trucking')])

        # Determine portfolios of current user based on their companies
        user_companies = request.env.user.company_ids
        portfolios = list({p.portfolio_id.name for p in user_companies if p.portfolio_id})
        show_all = 'General' in portfolios if portfolios else False

        # Driver availability counts (res.partner with is_driver True)
        Partner = request.env['res.partner']
        driver_domain = [('is_driver', '=', True)]
        if user_companies:
            driver_domain.append(('company_id', 'in', user_companies.ids))

        driver_ready = Partner.search_count(driver_domain + [('availability', '=', 'Ready')])
        driver_on_duty = Partner.search_count(driver_domain + [('availability', '=', 'On Duty')])
        driver_sakit = Partner.search_count(driver_domain + [('availability', '=', 'Sakit')])
        driver_cuti = Partner.search_count(driver_domain + [('availability', '=', 'Cuti')])
        driver_absent = Partner.search_count(driver_domain + [('availability', '=', 'Absent')])

        return {
            # 'total_dos': total_dos,
            # 'pending_dos': pending_dos,
            # 'done_dos': done_dos,
            # 'unmatch_dos': unmatch_dos,
            # 'match_dos': match_dos,
            # 'line_not_created_dos': line_not_created_dos,
            'trans_vehicle_count_ready': trans_vehicle_count_ready,
            'trans_vehicle_count_ready_on_book': trans_vehicle_count_ready_on_book,
            'trans_vehicle_count_on_going': trans_vehicle_count_on_going,
            'trans_vehicle_count_on_return': trans_vehicle_count_on_return,
            'trans_vehicle_count_not_ready': trans_vehicle_count_not_ready,
            'vli_vehicle_count_ready': vli_vehicle_count_ready,
            'vli_vehicle_count_ready_on_book': vli_vehicle_count_ready_on_book,
            'vli_vehicle_count_on_going': vli_vehicle_count_on_going,
            'vli_vehicle_count_on_return': vli_vehicle_count_on_return,
            'vli_vehicle_count_not_ready': vli_vehicle_count_not_ready,
            'truck_vehicle_count_ready': truck_vehicle_count_ready,
            'truck_vehicle_count_ready_on_book': truck_vehicle_count_ready_on_book,
            'truck_vehicle_count_on_going': truck_vehicle_count_on_going,
            'truck_vehicle_count_on_return': truck_vehicle_count_on_return,
            'truck_vehicle_count_not_ready': truck_vehicle_count_not_ready,
            # portfolio/visibility flags and driver cards data
            'portfolios': portfolios,
            'show_all': show_all,
            'driver_ready': driver_ready,
            'driver_on_duty': driver_on_duty,
            'driver_sakit': driver_sakit,
            'driver_cuti': driver_cuti,
            'driver_absent': driver_absent,
        }

    @http.route('/vehicle_dashboard/utilization_data', type='json', auth='user')
    def get_utilization_data(self):
        # data = request.env['vehicle.target.line'].search_read(
        #     [],
        #     ["year", "month", "total_target", "actual_target", "target_days_utilization"]
        # )
        # return data

        vehicles = request.env['fleet.vehicle'].search([])
        utilization_lines = request.env['vehicle.target.line'].search([])

        result = []
        for line in utilization_lines:
            result.append({
                'vehicle_name': line.vehicle_id.vehicle_name,
                'month': line.month,
                'year': line.year,
                'total_target': line.total_target,
                'actual_target': line.actual_target,
                'target_days_utilization': line.target_days_utilization,
            })

        return result


class CustomerDashboardController(http.Controller):
    @http.route('/customer_dashboard/data', type='json', auth='user')
    def get_customer_dashboard_data(self, start_date=None, end_date=None):
        domain = [('state', 'in', ['sale', 'done'])]  # Hanya transaksi yang sudah selesai

        # Tambahkan filter berdasarkan tanggal jika ada
        if start_date and end_date:
            start_date = fields.Datetime.to_string(fields.Datetime.from_string(start_date))
            end_date = fields.Datetime.to_string(fields.Datetime.from_string(end_date))
            domain.append(('date_order', '>=', start_date))
            domain.append(('date_order', '<=', end_date))

        # Menghitung total transaksi per pelanggan
        transactions_per_customer = request.env['sale.order'].read_group(
            domain,
            ['partner_id', 'amount_total'],
            ['partner_id']
        )

        # Format ulang data agar mudah digunakan di OWL
        formatted_data = []
        for record in transactions_per_customer:
            if record['partner_id']:
                formatted_data.append({
                    'customer_name': record['partner_id'][1],  # Ambil nama pelanggan
                    'transactions': record['amount_total']
                })

        return {
            'transactions_per_customer': formatted_data
        }


# class CustomerDashboardOutstandingController(http.Controller):
#
#     @http.route('/customer_dashboard_outstanding/data', type='json', auth='user')
#     def get_dashboard_data(self):
#         try:
#             # Query untuk mendapatkan Top 10 pelanggan dengan outstanding payment tertinggi
#             request.env.cr.execute("""
#                  SELECT
#                     p.id AS customer_id,
#                     p.name AS customer_name,
#                     SUM(m.amount_total  ) AS outstanding_amount,
#                     MAX(m.invoice_date_due) AS due_date
#                 FROM account_move m
#                 JOIN res_partner p ON m.partner_id = p.id
#                 WHERE m.move_type = 'out_invoice'
#                     AND m.invoice_date_due  < CURRENT_DATE
#                     and m.payment_state = 'not_paid'
#                     and m.state = 'posted'
#                 GROUP BY p.id, p.name
#                 ORDER BY outstanding_amount DESC
#                 LIMIT 10
#             """)
#
#             outstanding_customers = [
#                 {
#                     'customer_id': row[0],
#                     'customer_name': row[1],
#                     'outstanding_amount': row[2],
#                     'due_date': row[3].strftime('%Y-%m-%d') if row[3] else None
#                 }
#                 for row in request.env.cr.fetchall()
#             ]
#
#             return {
#                 'top_outstanding_customers': outstanding_customers,
#             }
#
#         except Exception as e:
#             return {'error': str(e)}

class AccountDashboardController(http.Controller):
    @http.route('/account_dashboard/top_outstanding', type='json', auth='user')
    def get_top_outstanding_customers(self, start_date=None, end_date=None):
        domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "!=", "paid"), ("partner_id", "!=", False)]

        if start_date:
            domain.append(("invoice_date", ">=", start_date))
        if end_date:
            domain.append(("invoice_date", "<=", end_date))

        invoices = request.env["account.move"].search(domain)

        customer_outstanding = {}
        for invoice in invoices:
            partner = invoice.partner_id
            if partner:
                customer_outstanding[partner.id] = customer_outstanding.get(partner.id, 0) + invoice.amount_residual

        top_customers = sorted(customer_outstanding.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "top_outstanding": [{"id": p[0], "name": request.env['res.partner'].browse(p[0]).name, "outstanding": p[1]}
                                for p in top_customers]
        }

    # class SaleOrderDashboardController(http.Controller):
    #
    #     @http.route('/sale_order_dashboard/data', type='json', auth='user')
    #     def dashboard_data(self):
    #         SaleOrder = request.env['sale.order'].sudo()
    #         SaleOrderLine = request.env['sale.order.line'].sudo()
    #
    #         # Total Sales
    #         total_sales = sum(SaleOrder.search([]).mapped('amount_total'))
    #
    #         # Sales per month
    #         monthly_totals = defaultdict(float)
    #         for order in SaleOrder.search([]):
    #             if order.date_order:
    #                 month = order.date_order.strftime('%Y-%m')
    #                 monthly_totals[month] += order.amount_total
    #         orders_per_month = [
    #             {'month': m, 'total': monthly_totals[m]}
    #             for m in sorted(monthly_totals)
    #         ]
    #
    #         # Sales by salesperson
    #         salesperson_totals = defaultdict(float)
    #         for order in SaleOrder.search([]):
    #             if order.user_id:
    #                 salesperson_totals[order.user_id.name] += order.amount_total
    #         sales_by_salesperson = [{'name': name, 'total': total}
    #                                 for name, total in salesperson_totals.items()]
    #
    #         # Sales by product
    #         product_totals = defaultdict(float)
    #         for line in SaleOrderLine.search([]):
    #             if line.product_id:
    #                 product_totals[line.product_id.name] += line.price_total
    #         sales_by_product = [{'name': name, 'total': total}
    #                             for name, total in product_totals.items()]
    #
    #         # Order status count
    #         status_count = defaultdict(int)
    #         for order in SaleOrder.search([]):
    #             status_count[order.state] += 1
    #
    #         # Top customers
    #         customer_totals = defaultdict(float)
    #         for order in SaleOrder.search([]):
    #             if order.partner_id:
    #                 customer_totals[order.partner_id.name] += order.amount_total
    #         top_customers = sorted(
    #             [{'name': name, 'total': total} for name, total in customer_totals.items()],
    #             key=lambda x: x['total'], reverse=True
    #         )[:10]
    #
    #         # Lead time (confirmation → delivery)
    #         lead_times = []
    #         for order in SaleOrder.search([('state', 'in', ['sale', 'done'])]):
    #             if order.date_order and order.commitment_date:
    #                 delta = (order.commitment_date - order.date_order).days
    #                 if delta >= 0:
    #                     lead_times.append(delta)
    #         lead_time_avg = round(sum(lead_times) / len(lead_times), 2) if lead_times else 0
    #
    #         # Conversion rate (quotations to SO)
    #         total_quotations = SaleOrder.search_count([('state', '=', 'draft')])
    #         total_confirmed = SaleOrder.search_count([('state', 'in', ['sale', 'done'])])
    #         conversion_rate = round((total_confirmed / (total_confirmed + total_quotations)) * 100, 2) if (total_confirmed + total_quotations) else 0
    #
    #         # Upcoming deliveries (next 7 days)
    #         today = fields.Date.today()
    #         next_week = today + timedelta(days=7)
    #         deliveries = SaleOrder.search([
    #             ('commitment_date', '>=', today),
    #             ('commitment_date', '<=', next_week),
    #             ('state', 'in', ['sale', 'done'])
    #         ])
    #         upcoming_deliveries = [{
    #             'name': d.name,
    #             'partner_name': d.partner_id.name,
    #             'date': d.commitment_date.strftime('%Y-%m-%d')
    #         } for d in deliveries]
    #
    #         return {
    #             'total_sales': total_sales,
    #             'orders_per_month': orders_per_month,
    #             'sales_by_salesperson': sales_by_salesperson,
    #             'sales_by_product': sales_by_product,
    #             'order_status_count': status_count,
    #             'top_customers': top_customers,
    #             'lead_time_avg': lead_time_avg,
    #             'conversion_rate': conversion_rate,
    #             'upcoming_deliveries': upcoming_deliveries,
    #         }

    @http.route('/dashboard_sales/summary', type='json', auth='user')
    def sales_summary(self):
        env = request.env
        today = fields.Date.today()
        first_day = today.replace(day=1)

        domain = [('date_order', '>=', first_day), ('state', 'in', ['sale', 'done'])]
        total_amount = env['sale.order'].search_read(domain, ['amount_total'])
        total_orders = env['sale.order'].search_count(domain)

        return {
            'total_revenue': sum([o['amount_total'] for o in total_amount]),
            'total_orders': total_orders,
        }

    @http.route('/dashboard_sales/monthly_trend', type='json', auth='user')
    def monthly_sales_trend(self):
        query = '''
            SELECT TO_CHAR(date_order, 'YYYY-MM') as month, SUM(amount_total)
            FROM sale_order
            WHERE state IN ('sale', 'done')
            GROUP BY TO_CHAR(date_order, 'YYYY-MM')
            ORDER BY month
        '''
        request.env.cr.execute(query)
        return [{'month': r[0], 'total': r[1]} for r in request.env.cr.fetchall()]

class DoMonitoringController(http.Controller):
    @http.route('/do_monitoring/data', type='json', auth='user')
    def get_dashboard_data(self, start_date=None, end_date=None):
        domain = []
        if start_date:
            domain.append(('date', '>=', start_date))
        if end_date:
            domain.append(('date', '<=', end_date))

        user_company_ids = request.env.user.company_ids.ids
        total_dos = request.env['fleet.do'].search_count(domain + [('company_id', 'in', user_company_ids)])
        pending_dos = request.env['fleet.do'].search_count(
            [('state', '=', 'draft'), ('status_do', 'in', ('DO Unmatch', 'DO Draft')), ('vehicle_id', '=', False),
                ('company_id', 'in', user_company_ids)])
        pending_approval_dos_by_spv = request.env['fleet.do'].search_count(
            [('vehicle_id', '!=', False), ('status_do', 'in', ('DO Unmatch', 'DO Draft')),
                ('state', '=', 'to_approve'), ('company_id', 'in', user_company_ids)])
        pending_approval_dos_by_cashier = request.env['fleet.do'].search_count(
            [('vehicle_id', '!=', False), ('status_do', '=', 'DO Match'), ('state', '=', 'approved_operation_spv'),
                ('company_id', 'in', user_company_ids)])
        pending_approval_dos_by_adh = request.env['fleet.do'].search_count(
            [('vehicle_id', '!=', False), ('status_do', '=', 'DO Match'), ('state', '=', 'approved_cashier'),
                ('company_id', 'in', user_company_ids)])
        pending_approval_dos_by_kacab = request.env['fleet.do'].search_count(
            [('vehicle_id', '!=', False), ('status_do', '=', 'DO Match'), ('state', '=', 'approved_adh'),
                ('company_id', 'in', user_company_ids)])
        pending_approval_dos_by_doc_delivery = request.env['fleet.do'].search_count(
            [('vehicle_id', '!=', False), ('status_do', '=', 'DO Match'), ('state', '=', 'approved_by_kacab'),
                ('company_id', 'in', user_company_ids)])
        done_dos = request.env['fleet.do'].search_count(
            [('state', '=', 'done'), ('status_do', '=', 'DO Match'), ('company_id', 'in', user_company_ids)])
        unmatch_dos = request.env['fleet.do'].search_count(
            [('status_do', '=', 'DO Unmatch'), ('company_id', 'in', user_company_ids)])
        match_dos = request.env['fleet.do'].search_count([('status_do', '=', 'DO Match'), ('status_document_status', 'in', ('Draft', 'draft')), ('company_id', 'in', user_company_ids)])
        ongoing_dos = request.env['fleet.do'].search_count(
            [('status_delivery', '=', 'on_going'), ('company_id', 'in', user_company_ids)])
        onreturn_dos = request.env['fleet.do'].search_count(
            [('status_delivery', '=', 'on_return'), ('company_id', 'in', user_company_ids)])
        line_not_created_dos = request.env['fleet.do'].search_count(
            [('state', '=', 'draft'), ('status_do', '=', 'DO Line not Created')])
        cancel_dos = request.env['fleet.do'].search_count(
            [('state', '=', 'cancel'), ('company_id', 'in', user_company_ids)])
        pending_approval_bop_by_adh = request.env['bop.line'].search_count(
            [('state', '=', 'approved_cashier'), ('fleet_do_id.state', '=', 'done'), ('is_settlement', '=', True), ('fleet_do_id.company_id', 'in', user_company_ids)])
        pending_approval_bop_by_kacab = request.env['bop.line'].search_count(
            [('state', '=', 'approved_adh'), ('fleet_do_id.state', '=', 'done'), ('is_settlement', '=', True), ('fleet_do_id.company_id', 'in', user_company_ids)])


        return {
            'total_dos': total_dos,
            'pending_dos': pending_dos,
            'pending_approval_dos_by_spv': pending_approval_dos_by_spv,
            'pending_approval_dos_by_cashier': pending_approval_dos_by_cashier,
            'pending_approval_dos_by_adh': pending_approval_dos_by_adh,
            'pending_approval_dos_by_kacab': pending_approval_dos_by_kacab,
            'pending_approval_dos_by_doc_delivery' : pending_approval_dos_by_doc_delivery,
            'done_dos': done_dos,
            'unmatch_dos': unmatch_dos,
            'match_dos': match_dos,
            'ongoing_dos':ongoing_dos,
            'onreturn_dos': onreturn_dos,
            'line_not_created_dos': line_not_created_dos,
            'cancel_dos': cancel_dos,
            'pending_approval_bop_by_adh': pending_approval_bop_by_adh,
            'pending_approval_bop_by_kacab': pending_approval_bop_by_kacab,

        }


class SoMonitoringController(http.Controller):
    @http.route('/so_monitoring/data', type='json', auth='user')
    def get_so_dashboard_data(self):
        allowed_company_ids = request.env.context.get('allowed_company_ids')
        if not allowed_company_ids:
            allowed_company_ids = request.env.user.company_ids.ids

        SaleOrder = request.env['sale.order']

        company_domain = [('company_id', 'in', allowed_company_ids)] if allowed_company_ids else []

        total_so = SaleOrder.search_count(company_domain)
        draft_so = SaleOrder.search_count(company_domain + [('state', '=', 'draft')])
        confirm_so = SaleOrder.search_count(company_domain + [('state', '=', 'sale')])
        without_do_so = SaleOrder.search_count(company_domain + [('order_line.do_id', '=', False)])
        with_do_so = SaleOrder.search_count(company_domain + [('order_line.do_id', '!=', False)])
        done_so_with_done_do = SaleOrder.search_count(company_domain + [
            ('state', '=', 'done'),
            ('order_line.do_id.state', '=', 'done'),
        ])

        return {
            'total_so': total_so,
            'draft_so': draft_so,
            'confirm_so': confirm_so,
            'without_do_so': without_do_so,
            'with_do_so': with_do_so,
            'done_so_with_done_do': done_so_with_done_do,
        }


class FleetMonitoringController(http.Controller):
    @http.route('/fleet_monitoring/data', type='json', auth='user')
    def get_fleet_monitoring_data(self):
        allowed_company_ids = request.env.context.get('allowed_company_ids')
        if not allowed_company_ids:
            allowed_company_ids = request.env.user.company_ids.ids

        company_tuple = tuple(allowed_company_ids) if allowed_company_ids else tuple()

        Partner = request.env['res.partner']
        FleetVehicle = request.env['fleet.vehicle']

        driver_domain = [('is_driver', '=', True)]
        if company_tuple:
            driver_domain.append(('company_id', 'in', company_tuple))

        total_drivers = Partner.search_count(driver_domain)
        ready_drivers = Partner.search_count(driver_domain + [('availability', '=', 'Ready')])
        not_ready_drivers = max(total_drivers - ready_drivers, 0)

        today = fields.Date.today()
        sim_expired_drivers = Partner.search_count(
            driver_domain + [('is_license_expiring', '=', True)]
        )

        company_condition = ""
        params = []
        if company_tuple:
            company_condition = " AND (rp.company_id IS NULL OR rp.company_id IN %s)"
            params.append(company_tuple)

        competency_sql = f"""
            SELECT rp.id,
                   CASE
                       WHEN latest_resume.type IS NOT NULL AND UPPER(latest_resume.type) = 'TRAINING' THEN 1
                       ELSE 0
                   END AS competence_status
            FROM res_partner rp
            LEFT JOIN hr_employee he ON he.work_contact_id = rp.id
            LEFT JOIN (
                SELECT hrl.employee_id,
                       hrlt.name AS type,
                       ROW_NUMBER() OVER (
                           PARTITION BY hrl.employee_id
                           ORDER BY hrl.date_end DESC NULLS LAST,
                                    hrl.date_start DESC NULLS LAST,
                                    hrl.id DESC
                       ) AS rn
                FROM hr_resume_line hrl
                LEFT JOIN hr_resume_line_type hrlt ON hrlt.id = hrl.line_type_id
            ) latest_resume ON he.id = latest_resume.employee_id AND latest_resume.rn = 1
            WHERE rp.is_driver IS TRUE{company_condition}
        """

        request.env.cr.execute(competency_sql, params)
        competency_rows = request.env.cr.fetchall()
        competency_needed_ids = [row[0] for row in competency_rows if row[1]]
        competency_needed = len(competency_needed_ids)

        vehicle_domain = []
        if company_tuple:
            vehicle_domain.append(('company_id', 'in', company_tuple))

        standby_vehicles = FleetVehicle.search_count(
            vehicle_domain + [('vehicle_status', '=', 'ready'), ('last_status_description_id.name_description', 'ilike', 'Ready for Use')]
        )
        on_delivery_vehicles = FleetVehicle.search_count(
            vehicle_domain + [('vehicle_status', '=', 'on_going')]
        )
        on_return_vehicles = FleetVehicle.search_count(
            vehicle_domain + [('vehicle_status', '=', 'on_return')]
        )

        return {
            'ready_drivers': ready_drivers,
            'not_ready_drivers': not_ready_drivers,
            'sim_expired_drivers': sim_expired_drivers,
            'competency_needed': competency_needed,
            'competency_needed_ids': competency_needed_ids,
            'standby_vehicles': standby_vehicles,
            'on_delivery_vehicles': on_delivery_vehicles,
            'on_return_vehicles': on_return_vehicles,
            'current_date': fields.Date.to_string(today),
        }


class InvoiceMonitoringController(http.Controller):

    @http.route('/invoice_monitoring/data', type='json', auth='user')
    def get_invoice_monitoring_data(self):
        """Get invoice statistics for dashboard cards"""
        # Get allowed company IDs
        allowed_company_ids = request.env.context.get('allowed_company_ids', [])

        # Use the model to get statistics
        return request.env['invoice.monitoring'].get_invoice_statistics()

    @http.route('/invoice_monitoring/details', type='json', auth='user')
    def get_invoice_details(self, filter_type):
        """Get detailed invoice data based on filter type"""
        # Get allowed company IDs
        allowed_company_ids = request.env.context.get('allowed_company_ids', [])

        # Use the model to get details
        return request.env['invoice.monitoring'].get_invoice_details(filter_type)
