from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import date_utils
from datetime import datetime, timedelta
import io, csv, zipfile
import json
import xlsxwriter

import logging
_logger = logging.getLogger(__name__)

class McmDriver(models.TransientModel):
    _name = 'mcm.driver'

    date = fields.Date('Tanggal penarikan')
        
    def generate_mcm_driver(self):
        
        FleetDo = self.env['fleet.do']
        allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])
        
        bop_recs = FleetDo.search([
            ('date', '=', self.date),
            ('company_id', 'in', allowed_company_ids),
            ('state', '!=', 'cancel'),
        ])
        
        for do in bop_recs:
            for line in do.bop_ids.filtered(lambda x: x.state != 'cancel'):
                if line.bop_no:
                    if line.state not in ('approved_by_kacab', 'done') and line.state != 'cancel':
                        raise UserError(_("Nomor BOP %s belum disetujui oleh Kepala Cabang")
                                % line.bop_no)
        
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/mcm_driver/report/csv_zip?wizard_id={self.id}',
            'target': 'self',
        }


    def set_excel_template(self, sheet, sheet_format, date):
        sheet.set_column('A:A', 26)  # NO
        sheet.set_column('B:B', 20)  # NAMP
        sheet.set_column('C:C', 18)  # ALA
        sheet.set_column('D:D', 13)  # IDK
        sheet.set_column('E:E', 14)  # IDK
        sheet.set_column('F:F', 16)  # MATU
        sheet.set_column('G:J', 18)  # TF
        sheet.set_column('K:K', 24)  # RE
        sheet.set_column('L:L', 13)  # RE
        sheet.set_column('M:M', 14)  # RE
        sheet.set_column('N:N', 9)  # RE
        sheet.set_column('O:O', 23)  # RE
        sheet.set_column('P:P', 9)  # RE
        sheet.write(4, 0, 'BANK MANDIRI - ANDRE TUWAN', sheet_format)
        sheet.write(5, 1, date, sheet_format)
        sheet.write(5, 2, 1520070116666, sheet_format)

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        date = self.browse([data['model_id']]).date
        first_date = date.replace(day=1)
        bop = self.env['fleet.do'].search([('bop_state', '!=', 'paid'), ('date', '>=', first_date), ('date', '<=', date)])
        mandiri_id = self.env['res.bank'].search([('name', '=', 'MANDIRI')])
        norek_mandiri = self.env['res.partner.bank'].search([('bank_id', 'in', mandiri_id.ids)]).mapped('acc_number')
        header = ['NO. REKENING', 'NAMA PENERIMA', 'ALAMAT PENERIMA', '', '', 'MATA UANG', 'NILAI YANG DI TRANSFER',
                  'REMARK', 'CUSTOMER REF.', 'FT SERVICES', 'BANK CODE', 'BENEF BANK NAME', 'BENEF BANK ADDRESS',
                  'EMAIL?', 'EMAIL', 'BENEF CITIZENSHIP']
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet1 = workbook.add_worksheet('Mandiri')
        sheet2 = workbook.add_worksheet('Beda Bank')
        border_head = workbook.add_format(
            {'font_size': 10,
             'bold': True, 'font_name': 'Arial',
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
            'border': True,})
        border_headr = workbook.add_format(
            {'font_size': 10,
             'bold': True, 'font_name': 'Arial',
             'align': 'right',
             'valign': 'vcenter',
             'text_wrap': True,
             'border': True,
             'num_format': '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'})
        border_body = workbook.add_format(
            {'font_size': 10,
             'bold': False, 'font_name': 'Arial',
             'align': 'center',
             'valign': 'vcenter',
             'text_wrap': True,
             'border': False, })
        border_bodyr = workbook.add_format(
            {'font_size': 10,
             'bold': False,
             'font_name': 'Arial',
             'num_format': '#,##0',
             'align': 'right',
             'valign': 'vcenter',
             'text_wrap': True,
             'border': False, })
        border_bodyl = workbook.add_format(
            {'font_size': 10,
             'bold': False, 'font_name': 'Arial',
             'align': 'left',
             'valign': 'vcenter',
             'text_wrap': True,
             'border': False, })
        border_headl = workbook.add_format(
            {'font_size': 10,
             'bold': True, 'font_name': 'Arial',
             'align': 'left',
             'valign': 'vcenter',
             'text_wrap': True,
             'border': True, })
        head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_name': 'Calibri', 'valign': 'top', 'text_wrap': True, 'font_size': 10,
             'num_format': '0',})
        head_right = workbook.add_format(
            {'align': 'right', 'bold': True, 'font_name': 'Calibri', 'valign': 'top', 'text_wrap': True, 'font_size': 10})
        column = 0
        row = 6
        self.set_excel_template(sheet1, head, date.strftime('%Y%m%d'))
        self.set_excel_template(sheet2, head, date.strftime('%Y%m%d'))
        for title in header:
            sheet1.write(row, column, title, head)
            sheet2.write(row, column, title, head)
            column += 1
        row += 1
        line_countm = 0
        line_countnm = 0
        total_m = 0
        total_nm = 0
        row_m = row
        row_nm = row
        for list_bop in bop:
            if list_bop.rekening_number in norek_mandiri:
                for bop_line in list_bop.bop_ids:
                    if bop_line.is_exported_to_mcm:
                        continue
                    sheet1.write(row_m, 0, list_bop.rekening_number, border_bodyr)
                    sheet1.write(row_m, 1, list_bop.rekening_name, border_bodyl)
                    sheet1.write(row_m, 2, list_bop.driver_id.city, border_bodyl)
                    sheet1.write(row_m, 5, list_bop.currency_id.name, border_bodyl)
                    sheet1.write(row_m, 6, bop_line.amount_paid, border_bodyr)
                    sheet1.write(row_m, 7, 'Gaji ' + date.strftime('%b %y'), border_bodyl)
                    sheet1.write(row_m, 8, 'Customer Reference', border_bodyl)
                    sheet1.write(row_m, 9, 'IBU', border_bodyl)
                    sheet1.write(row_m, 11, 'MANDIRI', border_bodyl)
                    sheet1.write(row_m, 12, 'Bank address', border_bodyl)
                    sheet1.write(row_m, 13, 'N', border_bodyl)
                    sheet1.write(row_m, 14, list_bop.driver_id.email, border_bodyl)
                    sheet1.write(row_m, 15, 'Y', border_body)
                    row_m += 1
                    line_countm += 1
                    total_m += bop_line.amount_paid if bop_line.amount_paid else 0
                    bop_line.write({'is_exported_to_mcm': True})
            if list_bop.rekening_number not in norek_mandiri:
                for bop_line in list_bop.bop_ids:
                    if bop_line.is_exported_to_mcm:
                        continue
                    sheet2.write(row_nm, 0, list_bop.rekening_number, border_bodyr)
                    sheet2.write(row_nm, 1, list_bop.rekening_name, border_bodyl)
                    sheet2.write(row_nm, 2, list_bop.driver_id.city, border_bodyl)
                    sheet2.write(row_nm, 5, list_bop.currency_id.name, border_bodyl)
                    sheet2.write(row_nm, 6, bop_line.amount_paid, border_bodyr)
                    sheet2.write(row_nm, 7, 'Gaji ' + date.strftime('%b %y'), border_bodyl)
                    sheet2.write(row_nm, 8, 'Customer Reference', border_bodyl)
                    sheet2.write(row_nm, 9, 'IBU', border_bodyl)
                    sheet2.write(row_nm, 10, '0020307', border_bodyr)
                    sheet2.write(row_nm, 11, self.env['res.partner.bank'].search([
                        ('acc_number', '=', list_bop.rekening_number)]).bank_id.name, border_bodyl)
                    sheet2.write(row_nm, 12, 'Bank address', border_bodyl)
                    sheet2.write(row_nm, 13, 'N', border_bodyl)
                    sheet2.write(row_nm, 14, list_bop.driver_id.email, border_bodyl)
                    sheet2.write(row_nm, 15, 'Y', border_body)
                    row_nm += 1
                    line_countnm += 1
                    total_nm += bop_line.amount_paid if bop_line.amount_paid else 0
                    bop_line.write({'is_exported_to_mcm': True})
        sheet1.write(5, 3, line_countm, head)
        sheet2.write(5, 3, line_countnm, head)
        sheet1.write(5, 4, total_m, head)
        sheet2.write(5, 4, total_nm, head)
        sheet1.write(row_m+1, 4,total_m + total_nm, border_bodyr)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
        
    def get_csv_report(self, response):
        self.ensure_one()

        wizard = self
        date = wizard.date or fields.Date.today()
        first_date = date.replace(day=1)

        FleetDo = self.env['fleet.do']
        bop_recs = FleetDo.search([
            ('bop_state', '!=', 'paid'),
            ('date', '>=', first_date),
            ('date', '<=', date),
        ])

        # bank Mandiri untuk memisahkan logic seperti di XLSX
        mandiri_id = self.env['res.bank'].search([('name', '=', 'MANDIRI')], limit=1)
        norek_mandiri = set(self.env['res.partner.bank'].search([
            ('bank_id', '=', mandiri_id.id)
        ]).mapped('acc_number')) if mandiri_id else set()

        header = [
            'NO. REKENING', 'NAMA PENERIMA', 'ALAMAT PENERIMA', '', '', 'MATA UANG',
            'NILAI YANG DI TRANSFER', 'REMARK', 'CUSTOMER REF.', 'FT SERVICES',
            'BANK CODE', 'BENEF BANK NAME', 'BENEF BANK ADDRESS',
            'EMAIL?', 'EMAIL', 'BENEF CITIZENSHIP'
        ]

        # Siapkan buffer CSV (dengan BOM supaya enak dibuka di Excel)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')

        # Tulis header
        writer.writerow(header)

        # Helper row builder: samakan urutan kolom dengan header
        def _writerow(rekening_number, rekening_name, alamat, mata_uang,
                      amount, remark, cust_ref, ft_services,
                      bank_code, benef_bank_name, benef_bank_addr,
                      email_flag, email, benef_citizenship):
            writer.writerow([
                rekening_number or '',
                rekening_name or '',
                alamat or '',
                '',  # kolom kosong seperti template
                '',  # kolom kosong seperti template
                mata_uang or '',
                f"{(amount or 0):.2f}",
                remark or '',
                cust_ref or '',
                ft_services or '',
                bank_code or '',
                benef_bank_name or '',
                benef_bank_addr or '',
                email_flag or '',
                email or '',
                benef_citizenship or '',
            ])

        # Tanggal untuk remark, sesuai XLSX: 'Gaji {Mon YY}'
        remark_text = f"Gaji {date.strftime('%b %y')}"

        # Loop data (gabungan kedua "sheet")
        for do in bop_recs:
            is_mandiri = (do.rekening_number in norek_mandiri) if do.rekening_number else False
            for bop_line in do.bop_ids:
                if bop_line.is_exported_to_mcm:
                    continue

                # nilai umum
                rekening_number = do.rekening_number
                rekening_name = do.rekening_name
                alamat = do.driver_id.city
                mata_uang = do.currency_id.name
                amount = bop_line.amount_paid
                cust_ref = 'Customer Reference'
                ft_services = 'IBU'
                benef_bank_addr = 'Bank address'
                email_flag = 'N'
                email = do.driver_id.email
                benef_citizenship = 'Y'

                if is_mandiri:
                    _writerow(
                        rekening_number, rekening_name, alamat, mata_uang,
                        amount, remark_text, cust_ref, ft_services,
                        bank_code='',                        # kosong untuk Mandiri
                        benef_bank_name='MANDIRI',          # sesuai XLSX
                        benef_bank_addr=benef_bank_addr,
                        email_flag=email_flag,
                        email=email,
                        benef_citizenship=benef_citizenship
                    )
                else:
                    bank_name = self.env['res.partner.bank'].search(
                        [('acc_number', '=', rekening_number)], limit=1
                    ).bank_id.name or ''
                    _writerow(
                        rekening_number, rekening_name, alamat, mata_uang,
                        amount, remark_text, cust_ref, ft_services,
                        bank_code='0020307',                 # sesuai XLSX bagian non-Mandiri
                        benef_bank_name=bank_name or '',
                        benef_bank_addr=benef_bank_addr,
                        email_flag=email_flag,
                        email=email,
                        benef_citizenship=benef_citizenship
                    )

                # tandai exported
                bop_line.write({'is_exported_to_mcm': True})

        # Tulis ke response (BOM + UTF-8)
        csv_text = buf.getvalue()
        buf.close()
        response.data = ("\ufeff" + csv_text).encode('utf-8')
        
    def get_csv_zip_report(self, response):
        self.ensure_one()
        date = self.date or fields.Date.today()
        first_date = date.replace(day=1)
        
        FleetDo = self.env['fleet.do']
        allowed_company_ids = self.env.context.get('allowed_company_ids', [self.env.company.id])
        bop_recs = FleetDo.search([
            ('date', '=', date),
            ('company_id', 'in', allowed_company_ids),
        ])

        mandiri_bank = self.env['res.bank'].search([('name', '=', 'MANDIRI')], limit=1)
        mandiri_accs = set(self.env['res.partner.bank'].search([
            ('bank_id', '=', mandiri_bank.id)
        ]).mapped('acc_number')) if mandiri_bank else set()

        header_columns = [
            'NO. REKENING','NAMA PENERIMA','ALAMAT PENERIMA','','','MATA UANG',
            'NILAI YANG DI TRANSFER','REMARK','CUSTOMER REF.','FT SERVICES',
            'BANK CODE','BENEF BANK NAME','BENEF BANK ADDRESS','EMAIL?','EMAIL','BENEF CITIZENSHIP'
        ]

        # === kumpulkan data dulu ===
        rows_m, rows_n = [], []
        count_m = count_n = 0
        total_m = total_n = 0.0
        remark = f"Gaji {date.strftime('%b %y')}"

        for do in bop_recs:
            is_mandiri = do.rekening_number in mandiri_accs if do.rekening_number else False
            for line in do.bop_ids:
                if line.bop_no:
                    if line.is_exported_to_mcm:
                        continue
                    common = [
                        do.rekening_number or '',
                        do.rekening_name or '',
                        do.driver_id.city or '',
                        '', '',  # kolom kosong sesuai template
                        do.currency_id.name or '',
                        f"{(line.amount_paid or 0):.2f}",
                        remark,
                        'Customer Reference',
                        'IBU',
                    ]
                    if is_mandiri:
                        
                        bank_acc = self.env['res.partner.bank'].search(
                            [('acc_number', '=', (do.rekening_number or '').replace(' ', ''))],
                            limit=1
                        )

                        bank = bank_acc.bank_id  # res.bank
                        bank_bic = bank.bic or ''          # SWIFT/BIC
                        bank_name = bank.name or ''
                        bank_addr = ", ".join(filter(None, [
                            getattr(bank, 'street', None),
                            getattr(bank, 'city', None),
                            getattr(getattr(bank, 'state', None), 'name', None) or getattr(getattr(bank, 'state_id', None), 'name', None),
                            getattr(getattr(bank, 'country', None), 'name', None) or getattr(getattr(bank, 'country_id', None), 'name', None),
                        ]))
                        
                        row = common + [
                            '',               # BANK CODE (Mandiri kosong)
                            'MANDIRI',
                            bank_addr,
                            'N',
                            do.driver_id.email or '',
                            'Y',
                        ]
                        rows_m.append(row)
                        count_m += 1
                        total_m += (line.amount_paid or 0.0)
                    else:
                        
                        bank_acc = self.env['res.partner.bank'].search(
                            [('acc_number', '=', (do.rekening_number or '').replace(' ', ''))],
                            limit=1
                        )

                        bank = bank_acc.bank_id  # res.bank
                        bank_bic = bank.bic or ''          # SWIFT/BIC
                        bank_name = bank.name or ''
                        bank_addr = ", ".join(filter(None, [
                            getattr(bank, 'street', None),
                            getattr(bank, 'city', None),
                            getattr(getattr(bank, 'state', None), 'name', None) or getattr(getattr(bank, 'state_id', None), 'name', None),
                            getattr(getattr(bank, 'country', None), 'name', None) or getattr(getattr(bank, 'country_id', None), 'name', None),
                        ]))

                        bank_name = self.env['res.partner.bank'].search(
                            [('acc_number', '=', do.rekening_number)], limit=1
                        ).bank_id.name or ''
                        row = common + [
                            bank_bic,
                            bank_name,
                            bank_addr,
                            'N',
                            do.driver_id.email or '',
                            'Y',
                        ]
                        rows_n.append(row)
                        count_n += 1
                        total_n += (line.amount_paid or 0.0)

                    # flag exported
                    line.write({'is_exported_to_mcm': True})

        # === tulis CSV Mandiri & Non-Mandiri dengan header ringkasan ===
        tmpl_date = date.strftime('%Y%m%d')
        tmpl_ref  = "1520070116666"  # contoh, sama seperti XLSX kamu

        def _write_csv(buffer, title, cnt, total, data_rows):
            w = csv.writer(buffer, lineterminator='\n')
            # 4 baris kosong (meniru posisi XLSX row=4 judul)
            # for _ in range(0):
            #     w.writerow([])
            # judul di kolom A
            # w.writerow([title])
            # baris ringkasan: B=tanggal, C=ref, D=jumlah, E=total
            # prefix apostrof untuk ref agar tidak jadi scientific notation
            w.writerow([title, tmpl_date, f"'{tmpl_ref}", cnt, f"{total:.2f}"])
            # baris kosong
            w.writerow([])
            # header kolom
            # w.writerow(header_columns)
            # data
            w.writerows(data_rows)

        buf_m, buf_n = io.StringIO(), io.StringIO()
        _write_csv(buf_m, 'ANDRE TUWAN', count_m, total_m, rows_m)
        _write_csv(buf_n, 'ANDRE TUWAN', count_n, total_n, rows_n)

        # ZIP-kan dua CSV
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"Mandiri - {date.strftime('%b %y')}.csv",
                        ("\ufeff" + buf_m.getvalue()).encode('utf-8'))  # BOM + UTF-8
            zf.writestr(f"Beda Bank - {date.strftime('%b %y')}.csv",
                        ("\ufeff" + buf_n.getvalue()).encode('utf-8'))

        response.data = zip_buf.getvalue()
        