from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_print_custom_invoice(self):
        """Action untuk print custom invoice PDF"""
        if not self.ids:
            raise UserError("Please select an invoice to print.")

        # Return action untuk generate PDF report
        return self.env.ref('jst_custom_pdf_report.action_report_custom_invoice').report_action(self)

    def get_static_invoice_data(self):
        """Method untuk mendapatkan data statis sesuai dengan format referensi KALLA TRANSPORT"""
        return {
            'company_name': 'KALLA TRANSPORT',
            'company_address': 'Jl. Sutan - Pallatta, Makassar',
            'bank_info': 'MANDIRI 1520000004115',
            'invoice_no': 'LGC/003/BPI08/0825',
            'period': '09-15 AGUSTUS 2025',
            'bill_to': {
                'name': 'PT. BUMI PUTRA INDONESIA',
                'address': 'JALAN AP PETTARANI 3 B NO 26,',
                'address2': 'TAMAMAUNG, PANAKKUKANG',
                'address3': 'KOTA MAKASSAR SULAWESI',
                'address4': 'SELATAN',
                'npwp': 'NPWP : 0200 ( 000 000 000 )'
            },
            'invoice_details': {
                'invoice_date': '9/19/25',
                'payment_terms': '30',
                'due_date': '9/19/25',
                'line_total': '311,900,000.00',
                'sales_tax': '3,430,900.00',
                'shipping': '0.00',
                'total': '315,330,900.00',
                'payments': '0.00',
                'credits': '0.00',
                'financial_charges': '0.00'
            },
            'service_item': {
                'no': '1',
                'description': 'BIAYA PENGIRIMAN BARANG PERIODE 09-15 AGUSTUS 2025',
                'uom': 'Unit',
                'quantity': '1',
                'unit_price': '311,900,000',
                'amount': '311,900,000.00'
            },
            'signature': {
                'signed_by': 'Irfan',
                'title': 'Administration Senior Supervisor'
            },
            'payment_info': {
                'send_to': 'Jl. Sultan - Pallatta',
                'city': 'Makassar',
                'bank': 'MANDIRI 1520000004115'
            },
            # Data untuk halaman kedua (faktur pajak) - tetap menggunakan format lama
            'tax_invoice': {
                'company_name': 'BUMI POPO LOLI',
                'company_address': 'Masjid Agung, KOTA MAKASSAR',
                'tax_number': '#0099999999992000000000',
                'serial_code': '09002500123456789',
                'npwp': '0099999999992000',
                'buyer': {
                    'name': 'QWERTY ASAS',
                    'address': 'JALAN AP SEMBRANI 5 B NO. 9, RT 000, RW 000, TAMAMAUNG, PANAKKUKANG, KOTA MAKASSAR, SULAWESI SELATAN 90231',
                    'npwp': '0200999999999000',
                    'email': 'QWERTYASAS@GMAIL.COM'
                },
                'service': {
                    'code': '090103',
                    'name': 'PENGIRIMAN BARANG',
                    'amount': 311900000,
                    'ppn_amount': 3430900
                }
            },
            'date': 'Makassar 19 Agustus 2025',
            'reference': 'LGC/1212/BPI08/0825'
        }