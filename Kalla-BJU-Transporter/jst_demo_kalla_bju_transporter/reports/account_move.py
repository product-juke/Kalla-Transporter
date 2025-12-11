from odoo import models, fields
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def get_custom_lines(self):
        """Contoh method untuk ambil detail invoice line"""
        lines = []
        for line in self.invoice_line_ids:
            lines.append({
                'product': line.product_id.display_name or "-",
                'description': line.name or "-",
                'uom': line.product_uom_id.name if line.product_uom_id else "-",
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'amount': line.price_subtotal,
            })
        return lines

    def get_invoice_detail_orders(self):
        so_do_items = []
        lines = []
        main_company = self.env['res.company'].search([
            ('id', '=', 1),
        ], limit=1)

        sum_price_total = 0
        sum_price_total_in_vli = 0
        sum_tax_ppn_1_1 = 0
        sum_tax_pph_23 = 0
        sum_grand_total = 0

        for line in self.invoice_line_ids:
            query = """
                SELECT invoice_line_id, order_line_id FROM sale_order_line_invoice_rel solir
                WHERE solir.invoice_line_id = %s
                LIMIT 1
            """
            self.env.cr.execute(query, (line.id,))
            result = self.env.cr.dictfetchone()

            _logger.info(f'On Print Invoice Detail Order => Query Result -> {result}')

            if result and 'order_line_id' in result:
                order_line = self.env['sale.order.line'].search([
                    ('id', '=', result['order_line_id']),
                ], limit=1)
                order = order_line.order_id

                _logger.info(f'On Print Invoice Detail Order => Order Line -> {order_line}')

                item = {
                    'do_id': order_line.do_id,
                    'order_id': order,
                }
                if item not in so_do_items:
                    so_do_items.append(item)

        for item in so_do_items:
            geofence_unloading_code = item['do_id'].geofence_unloading_id.geo_code
            multiplied_by = {
                'ritase': 'qty_ritase',
                'volume': 'qty_kubikasi',
                'tonase': 'qty_tonase',
            }

            invoiced_by = None
            if item['order_id'].product_category_id.name.lower() == 'transporter':
                invoiced_by = multiplied_by[item['order_id'].contract_id.invoiced_by]

            sale_order_options = self.env['sale.order.option'].search([
                ('order_id', '=', item['order_id'].id),
            ])

            for option in sale_order_options:
                price_total = option.price_unit * option[invoiced_by] if invoiced_by else 0
                price_total_in_vli = option.price_unit * option.quantity
                tax_ppn_1_1 = price_total * 0.011
                tax_pph_23 = price_total * 0.02
                grand_total = price_total + tax_ppn_1_1 - tax_pph_23

                # Akumulasi untuk total
                sum_price_total += price_total
                sum_tax_ppn_1_1 += tax_ppn_1_1
                sum_tax_pph_23 += tax_pph_23
                sum_grand_total += grand_total
                sum_price_total_in_vli += price_total_in_vli

                delivery_category = item['do_id'].vehicle_id.category_id.program_category_id.name
                if str(item['do_id'].delivery_category_id.name).lower() == 'self drive':
                    delivery_category = 'Self Drive'

                data = {
                    'vendor_name': main_company.name,
                    'destination_name': option.destination_id.name,
                    'origin_name': option.origin_id.name,
                    'store_name': option.product_id.name,
                    'manifest': option.name,
                    'unit_type': item['do_id'].vehicle_id.category_id.name,
                    'delivery_category': delivery_category,
                    'license_plate': item['do_id'].vehicle_id.license_plate,
                    'vin_sn': item['do_id'].vehicle_id.vin_sn,
                    'period': item['order_id'].date_order,
                    'price_total': f"{price_total:,.0f}",
                    'price_total_in_vli': f"{price_total_in_vli:,.0f}",
                    'tax_ppn_1_1': f"{tax_ppn_1_1:,.0f}",
                    'tax_pph_23': f"{tax_pph_23:,.0f}",
                    'grand_total': f"{grand_total:,.0f}",
                }
                lines.append(data)

        total = {
            'price_total': f"{sum_price_total:,.0f}",
            'tax_ppn_1_1': f"{sum_tax_ppn_1_1:,.0f}",
            'tax_pph_23': f"{sum_tax_pph_23:,.0f}",
            'grand_total': f"{sum_grand_total:,.0f}",
            'price_total_in_vli': f"{sum_price_total_in_vli:,.0f}",
        }

        return {
            'total': total,
            'rows': lines,
            'terbilang': self.terbilang(int(sum_grand_total)),
            'company': main_company,
            'current_date': self.format_tanggal_indo(fields.Date.today())
        }

    def terbilang(self, n):
        angka = ["", "Satu", "Dua", "Tiga", "Empat", "Lima",
                 "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]

        hasil = ""
        if n < 12:
            hasil = angka[n]
        elif n < 20:
            hasil = self.terbilang(n - 10) + " Belas"
        elif n < 100:
            hasil = self.terbilang(n // 10) + " Puluh " + self.terbilang(n % 10)
        elif n < 200:
            hasil = "Seratus " + self.terbilang(n - 100)
        elif n < 1000:
            hasil = self.terbilang(n // 100) + " Ratus " + self.terbilang(n % 100)
        elif n < 2000:
            hasil = "Seribu " + self.terbilang(n - 1000)
        elif n < 1000000:
            hasil = self.terbilang(n // 1000) + " Ribu " + self.terbilang(n % 1000)
        elif n < 1000000000:
            hasil = self.terbilang(n // 1000000) + " Juta " + self.terbilang(n % 1000000)
        elif n < 1000000000000:
            hasil = self.terbilang(n // 1000000000) + " Miliar " + self.terbilang(n % 1000000000)
        else:
            hasil = self.terbilang(n // 1000000000000) + " Triliun " + self.terbilang(n % 1000000000000)

        return hasil.strip()

    def format_tanggal_indo(self, date_obj):
        if not date_obj:
            return ""

        bulan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]

        # pastikan date_obj itu datetime/date/string
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
            except ValueError:
                return date_obj  # kalau format tidak sesuai

        hari = date_obj.day
        bulan_nama = bulan[date_obj.month - 1]
        tahun = date_obj.year

        return f"{hari} {bulan_nama} {tahun}"