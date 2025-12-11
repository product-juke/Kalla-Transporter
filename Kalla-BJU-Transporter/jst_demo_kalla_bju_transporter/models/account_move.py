# -*- coding: utf-8 -*-
from datetime import timedelta, datetime
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from dateutil.relativedelta import relativedelta
import re
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ['account.move', 'tier.validation', 'portfolio.view.mixin']
    _state_from = ["draft"]
    _state_to = ["posted"]

    _tier_validation_manual_config = False

    fleet_id = fields.Many2one('fleet.do')
    bop_line_ids = fields.One2many(
        comodel_name='bop.line',
        inverse_name='vendor_bill_id',
        string='BOP Lines'
    )
    bop_count = fields.Integer(string='BOP Count', compute='_compute_bop_count', store=False)
    tp_dpp_nilai_lain = fields.Monetary(
        string='DPP Nilai Lain',
        readonly=True,
        compute="_compute_tp_dpp_nilai_lain",
        currency_field='company_currency_id',
    )
    date_sent_to_customer = fields.Date('Date Sent to Customer', tracking=True)
    aging_invoice_overdue = fields.Date(
        string='Aging Overdue Date',
        readonly=True,
        store=True,
        compute="_compute_aging_invoice_overdue",
    )
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        store=True, readonly=False, precompute=True,
        context={'active_test': False},
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    can_edit_lines_tax_ids = fields.Boolean(compute="_compute_can_edit_lines_tax_ids")
    tax_invoicing_method = fields.Selection([
        ('total_invoice', 'Total Invoice'),
        ('line_invoice', 'Line Invoice'),
    ], tracking=True, related='partner_id.tax_invoicing_method', readonly=True)
    periode_rekapan = fields.Char('Period Rekapan')

    @api.model
    def create(self, vals_list):
        """Override create method to ensure dpp_nilai_lain is computed correctly"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        records = super().create(vals_list)

        # Force computation of dpp_nilai_lain after record creation
        for record in records:
            if record.line_ids:
                record._compute_tp_dpp_nilai_lain()

        return records

    def write(self, vals):
        if 'name' in vals and vals['name'] and vals['name'].startswith('BILL-'):
            vals['name'] = vals['name'].replace('-', '/')
            
        if 'name' in vals and vals['name'] and vals['name'].startswith('INV-'):
            vals['name'] = vals['name'].replace('-', '/')

        dpp_affecting_fields = ['invoice_line_ids', 'line_ids']
        should_recompute_dpp = any(field in vals for field in dpp_affecting_fields)

        if 'invoice_line_ids' in vals:
            for command in vals.get('invoice_line_ids', []):
                if isinstance(command, (list, tuple)) and len(command) >= 3:
                    if command[0] in (0, 1, 2):  # create, update, delete
                        should_recompute_dpp = True
                        break

        result = super().write(vals)

        if not self.env.context.get('skip_name_fix'):
            for rec in self:
                if rec.name and rec.name.startswith('BILL-'):
                    fixed = rec.name.replace('-', '/')
                    if fixed != rec.name:
                        rec.with_context(
                            skip_name_fix=True,
                            tracking_disable=True
                        ).write({'name': fixed})
                        
                if rec.name and rec.name.startswith('INV-'):
                    fixed = rec.name.replace('-', '/')
                    if fixed != rec.name:
                        rec.with_context(
                            skip_name_fix=True,
                            tracking_disable=True
                        ).write({'name': fixed})

        if should_recompute_dpp:
            for record in self:
                record._compute_tp_dpp_nilai_lain()

        return result

    @api.onchange('invoice_line_ids', 'line_ids')
    def _onchange_lines_dpp(self):
        """Onchange method to update dpp_nilai_lain in real-time when lines change"""
        if self.line_ids:
            self._compute_tp_dpp_nilai_lain()

    @api.depends(
        'invoice_line_ids.quantity',
        'invoice_line_ids.price_unit',
    )
    def _compute_tp_dpp_nilai_lain(self):
        for rec in self:
            total = 0
            for line in rec.line_ids:
                total += line.tp_dpp_nilai_lain
            rec.tp_dpp_nilai_lain = int(float_round(total, 2))

    @api.depends('bop_line_ids')
    def _compute_bop_count(self):
        for move in self:
            move.bop_count = len(move.bop_line_ids)

    def action_view_bop(self):
        self.ensure_one()
        action = self.env.ref('jst_demo_kalla_bju_transporter.bop_line_action').read()[0]
        action['domain'] = [('vendor_bill_id', '=', self.id)]

        # paksa list dulu, baru form (meski hanya 1 baris tetap tampil tree)
        tree_view = self.env.ref('jst_demo_kalla_bju_transporter.bop_line_view_tree', raise_if_not_found=False)
        form_view = self.env.ref('jst_demo_kalla_bju_transporter.bop_line_view_form', raise_if_not_found=False)
        action.update({
            'name': _('BOP'),
            'view_mode': 'tree,form',
            'views': [((tree_view and tree_view.id) or False, 'tree'),
                      ((form_view and form_view.id) or False, 'form')],
        })
        return action

    def button_cancel(self):
        # Panggil parent untuk eksekusi normal cancel
        res = super(AccountMove, self).button_cancel()

        # Loop per record yang di-cancel
        for move in self:
            # Cek apakah move ini hasil dari proses BOP Vendor Bill
            if move.move_type == 'in_invoice' and move.invoice_origin:
                # Ambil info BOP No dari invoice_origin
                bop_nos = [part.split(' - ')[0].strip() for part in move.invoice_origin.split(',')]
                bop_lines = self.env['bop.line'].search([('bop_no', 'in', bop_nos)])

                if bop_lines:
                    bop_lines.write({'is_created_vendor_bill': False})
        return res

    def _get_or_create_analytic_account(self, analytic_param):
        """Get existing analytic account or create new one based on product category name"""
        if not analytic_param:
            return False

        vehicle_name = analytic_param[0]
        no_lambung = analytic_param[3]
        product_category_name = analytic_param[4]
        model_category_name = analytic_param[5]

        # Search for existing analytic account
        analytic_account = self.env['account.analytic.account'].search([
            ('name', '=', vehicle_name)  # Vehicle Name
        ], limit=1)

        # Create if doesn't exist
        if not analytic_account:
            # Get or create the analytic plan
            plan_name = f"{product_category_name} / {model_category_name}"
            analytic_plan = self.env['account.analytic.plan'].search([
                ('complete_name', '=', plan_name)
            ], limit=1)

            print('analytic_plan', analytic_plan)

            if not analytic_plan:
                # Create the analytic plan if it doesn't exist
                analytic_plan = self.env['account.analytic.plan'].create({
                    'name': plan_name,
                    'description': f'Analytic plan for {product_category_name} - {model_category_name}',
                    'default_applicability': 'optional',  # or 'mandatory' based on your needs
                })

            # Create the analytic account
            analytic_account = self.env['account.analytic.account'].create({
                'name': vehicle_name,
                'code': no_lambung[:11] if no_lambung else False,  # Limit code to 10 chars, handle None
                'plan_id': analytic_plan.id,  # Set the mandatory plan_id field
            })

        return analytic_account

    def _get_or_create_analytic_plan(self, product_category_name, model_category_name):
        """Helper method to get or create analytic plan"""
        plan_name = f"{product_category_name} / {model_category_name}"

        # Search for existing plan
        analytic_plan = self.env['account.analytic.plan'].search([
            ('complete_name', '=', plan_name)
        ], limit=1)

        # Create if doesn't exist
        if not analytic_plan:
            # Check if parent plan exists (product_category_name)
            parent_plan = self.env['account.analytic.plan'].search([
                ('name', '=', product_category_name)
            ], limit=1)

            if not parent_plan:
                # Create parent plan first
                parent_plan = self.env['account.analytic.plan'].create({
                    'name': product_category_name,
                    'description': f'Parent plan for {product_category_name}',
                    'default_applicability': 'optional',
                })

            # Create child plan
            analytic_plan = self.env['account.analytic.plan'].create({
                'name': model_category_name,
                'parent_id': parent_plan.id,
                'description': f'Plan for {model_category_name} under {product_category_name}',
                'default_applicability': 'optional',
            })

        return analytic_plan

    def _update_move_lines_analytic_distribution(self):
        lines_to_update = self.line_ids
        current_line_id = None

        for line in lines_to_update:
            current_line_id = line.id
            query_get_do_po_line_rel = """
            select
                fv.vehicle_name, dplr.po_line_id, dplr.do_id, fv.no_lambung, pc.name, fvmc.name
            from
                do_po_line_rel dplr
            join fleet_do fd on
                fd.id = dplr.do_id
            join fleet_vehicle fv on
                fv.id = fd.vehicle_id
            join fleet_vehicle_model_category fvmc on
                fvmc.id = fv.category_id
            join product_category pc on
                pc.id = fv.product_category_id
            join sale_order_line_invoice_rel solir on
                solir.order_line_id = dplr.po_line_id 
            where solir.invoice_line_id = %s
            limit 1
            """

            self.env.cr.execute(query_get_do_po_line_rel, (line.id,))
            vehicle = self.env.cr.fetchone()

            if vehicle:
                analytic_account = self._get_or_create_analytic_account(vehicle)
                analytic_distribution = {str(analytic_account.id): 100}

                line.write({
                    'analytic_distribution': analytic_distribution,
                })

    @api.onchange('product_category_id')
    def _onchange_product_category_id(self):
        """Update analytic distribution when product category changes"""
        if self.product_category_id and self.is_lms(self.env.company.portfolio_id.name):
            self._update_move_lines_analytic_distribution()

    def _generate_inv_log_name(self, kode_perusahaan, kode_jenis, company, date=None):
        
        seq = self._ensure_monthly_sequence(
            kode_perusahaan=kode_perusahaan,
            kode_jenis=kode_jenis,
            company=company,
            type='out_invoice',
            prefix='INV/',
            suffix=f'/{kode_perusahaan}/%(range_month)s/%(range_year)s',
        )
        
        seq_date = date or fields.Date.context_today(self)
        code = f'custom.invoice.{kode_perusahaan}'
        nomor_urut = seq.with_context(ir_sequence_date=seq_date).next_by_id()
        return f'{nomor_urut}'
        # nomor_urut = self.env['ir.sequence'].with_context(ir_sequence_date=seq_date).next_by_code(code)
        # return f'{nomor_urut}'
        # return f'{nomor_urut}/{kode_perusahaan}/{bulan}/{tahun}'

    def _generate_default_inv_name(self):
        # return '/'
    
        # return self.env['ir.sequence'].next_by_code('account.move.inv') or '/'
        
        nomor_urut = self.env['ir.sequence'].next_by_code('account.move.inv') or '00000'
        now = datetime.today()
        return f"INV-{now.year}-{str(now.month).zfill(2)}-{nomor_urut}"

    def _generate_inv_bill_name(self, kode_perusahaan, kode_jenis, company, date=None):
        self._ensure_monthly_sequence(
            kode_perusahaan=kode_perusahaan,
            kode_jenis=kode_jenis,
            company=company,
            prefix='BILL/',
            # penting: simpan suffix di ir.sequence (bukan manual di return)
            suffix=f'/{kode_perusahaan}/{kode_jenis}/%(range_month)s/%(range_year)s',
        )
        seq_date = date or fields.Date.context_today(self)
        code = f'custom.bill.{kode_jenis}.{kode_perusahaan}'
        # pastikan pakai tanggal dokumen untuk pilih date_range yg benar
        return self.env['ir.sequence'].with_context(ir_sequence_date=seq_date).next_by_code(code)

    @api.model
    def _ensure_monthly_sequence(self, *, kode_perusahaan, kode_jenis, company, type=None,
                                name=None, prefix=None, suffix=None, padding=5):
        
        if type == 'out_invoice':
            code = f'custom.invoice.{kode_perusahaan}'
            name = name or f'Custom Inv {kode_perusahaan}'
            padding = 3
        else: 
            code = f'custom.bill.{kode_jenis}.{kode_perusahaan}'
            name = name or f'Custom Bill {kode_jenis} {kode_perusahaan}'
            padding = 5
        
        # seq = self.env['ir.sequence'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        seq = self.env['ir.sequence'].search([('code', '=', code)], limit=1)
        vals = {
            'name': name,
            'code': code,
            'implementation': 'no_gap',
            'use_date_range': True,
            'company_id': False,
            'padding': padding,
        }
        if prefix is not None:
            vals['prefix'] = prefix
        if suffix is not None:
            vals['suffix'] = suffix

        if not seq:
            seq = self.env['ir.sequence'].create(vals)
        else:
            seq.write({k: v for k, v in vals.items() if k in ('prefix', 'suffix', 'use_date_range', 'padding') and v is not None})

        seq_date = fields.Date.context_today(self)
        start = seq_date.replace(day=1)
        end = (start + relativedelta(months=1)) - relativedelta(days=1)
        dr = self.env['ir.sequence.date_range'].search([
            ('sequence_id', '=', seq.id), ('date_from', '=', start), ('date_to', '=', end)
        ], limit=1)
        if not dr:
            self.env['ir.sequence.date_range'].create({
                'sequence_id': seq.id,
                'date_from': start,
                'date_to': end,
                'number_next': 1,
            })
        return seq

    def _generate_default_bill_name(self):
        nomor_urut = self.env['ir.sequence'].next_by_code('account.move.bill') or '000'
        now = datetime.today()
        return f"BILL-{now.year}-{str(now.month).zfill(2)}-{nomor_urut}"

    # @api.constrains('name')
    # def _check_name_length(self):
    #     for record in self:
    #         if record.move_type == 'out_invoice' and record.name and len(record.name) > 20:
    #             raise ValidationError(
    #                 _("Panjang karakter field 'Name' tidak boleh lebih dari 20 karakter untuk Out Invoice."))

    @api.model_create_multi
    def create(self, vals_list):
        # for vals in vals_list:
        #     move_type = vals.get('move_type')
        #     if move_type in ['out_invoice', 'in_invoice'] and not vals.get('name'):
        #         company = self.env['res.company'].browse(vals.get('company_id')) if vals.get(
        #             'company_id') else self.env.company
        #         kode_perusahaan = company.company_code or 'LMKS'
        #         portofolio_name = company.portfolio_id.name if company.portfolio_id else ''

        #         portofolio_mapping = {
        #             'Transporter': 'TRP',
        #             'Trucking': 'TRU',
        #             'VLI': 'VLI'
        #         }

        #         if portofolio_name in portofolio_mapping:
        #             kode_jenis = portofolio_mapping[portofolio_name]
        #             if move_type == 'out_invoice':
        #                 vals['name'] = self._generate_inv_log_name(kode_perusahaan, kode_jenis, company)
        #             elif move_type == 'in_invoice':
        #                 vals['name'] = self._generate_inv_bill_name(kode_perusahaan, kode_jenis, company)
        #         else:
        #             if move_type == 'out_invoice':
        #                 vals['name'] = self._generate_default_inv_name()
        #             elif move_type == 'in_invoice':
        #                 vals['name'] = self._generate_default_bill_name()

        # Create the moves
        moves = super().create(vals_list)

        # Update analytic distribution for each created move
        for move in moves:
            if self.is_lms(move.env.company.portfolio_id.name):
                move._update_move_lines_analytic_distribution()

                combined_distribution = {}
                trade_payable_accounts = move.line_ids.filtered(lambda x: x.account_id.code == '21100010' or x.account_id.name == 'Trade Receivable')
                ar_accounts = move.line_ids.filtered(lambda x: x.account_id.code == '11210001' or x.account_id.name == 'Account Receivable')
                tax_journal_items = move.line_ids.filtered(lambda x: x.display_type == 'tax')
                for line in move.invoice_line_ids:
                    if line.analytic_distribution:
                        combined_distribution.update(line.analytic_distribution)

                # Update receivable account dengan gabungan analytic distribution
                if combined_distribution:
                    for item in trade_payable_accounts:
                        item.sudo().write({
                            'analytic_distribution': combined_distribution
                        })
                    for item in tax_journal_items:
                        item.sudo().write({
                            'analytic_distribution': combined_distribution
                        })
                    for item in ar_accounts:
                        item.sudo().write({
                            'analytic_distribution': combined_distribution
                        })

        return moves

    def unlink(self):
        for move in self:
            if move.move_type == "in_invoice":
                bop_lines = self.env['bop.line'].search([('vendor_bill_id', '=', move.id)])
                bop_lines.write({
                    'is_created_vendor_bill': False,
                })
                bop_lines.fleet_do_id.write({
                    'remaining_bop_driver_has_been_converted_to_bill': False,
                })
        return super().unlink()
    
    # def action_post(self):
    #     res = super().action_post()
    #     for move in self:
    #         if move.move_type == 'in_invoice':
    #             self.env['bop.line'].search([('vendor_bill_id', '=', move.id)]).write({
    #                 'is_created_vendor_bill': True
    #             })
                
    #         if move.move_type in ('out_invoice', 'in_invoice'): #and (not move.name or move.name == '/'):
    #             company = move.company_id
    #             kode_perusahaan = company.company_code or 'LMKS'
    #             portofolio_name = company.portfolio_id.name or ''

    #             portofolio_mapping = {
    #                 'Transporter': 'TRP',
    #                 'Trucking':    'TRU',
    #                 'VLI':         'VLI',
    #             }
            
    #             if portofolio_name in portofolio_mapping:
    #                 kode_jenis = portofolio_mapping[portofolio_name]
                    
    #                 company = move.company_id
    #                 if move.move_type == 'out_invoice':
    #                     # old
    #                     # move.name = self._generate_inv_log_name(kode_perusahaan, kode_jenis, company)
                        
    #                     seq = move._ensure_monthly_sequence(
    #                         kode_perusahaan=company.company_code,
    #                         kode_jenis=company.portfolio_id.name,
    #                         company=company,
    #                         type='out_invoice',
    #                         prefix='INV/',
    #                         suffix=f'/{company.company_code}/%(range_month)s/%(range_year)s',
    #                     )
                        
    #                     seq_date = move.invoice_date or fields.Date.context_today(self)
    #                     nomor_urut = seq.with_context(ir_sequence_date=seq_date).next_by_id()
    #                     _logger.info(f"PUJI")
    #                     _logger.info(f"Nomor Urut: {nomor_urut}")
    #                     _logger.info(f"YANTO")
    #                     move.write({'name': nomor_urut})
                        
    #                 else:  # in_invoice
    #                     # old
    #                     # move.name = self._generate_inv_bill_name(kode_perusahaan, kode_jenis, company)
                        
    #                     seq = self._ensure_monthly_sequence(
    #                         kode_perusahaan=kode_perusahaan,
    #                         kode_jenis=kode_jenis,
    #                         company=company,
    #                         prefix='BILL/',
    #                         suffix=f'/{kode_perusahaan}/{kode_jenis}/%(range_month)s/%(range_year)s',
    #                     )
                        
    #                     seq_date = move.invoice_date or fields.Date.context_today(self)
    #                     nomor_urut =  seq.with_context(ir_sequence_date=seq_date).next_by_id()
    #                     move.write({'name': nomor_urut})
    #             else:
    #                 if move.move_type == 'out_invoice':
    #                     move.name = self._generate_default_inv_name()
    #                 else: # in_invoice
    #                     move.name = self._generate_default_bill_name()
                
    #     return res
    
    def action_post(self):
        for move in self:
            if move.move_type in ('out_invoice', 'in_invoice'):
                company = move.company_id
                kode_perusahaan = company.company_code or 'LMKS'
                portofolio_name = (company.portfolio_id.name or '')
                mapping = {'Transporter':'TRP', 'Trucking':'TRU', 'VLI':'VLI'}
                if portofolio_name in mapping:
                    kode_jenis = mapping[portofolio_name]

                    # 1) kosongkan dulu agar Odoo tidak pakai nama lama
                    if move.name and move.name != '/':
                        move.name = '/'

                    # 2) siapkan sequence bulanan yang tepat
                    if move.move_type == 'out_invoice':
                        seq = move._ensure_monthly_sequence(
                            kode_perusahaan=company.company_code,
                            kode_jenis=company.portfolio_id.name,
                            company=company,
                            type='out_invoice',
                            prefix='INV/',
                            suffix=f'/{company.company_code}/%(range_month)s/%(range_year)s',
                        )
                    else:
                        seq = move._ensure_monthly_sequence(
                            kode_perusahaan=kode_perusahaan,
                            kode_jenis=kode_jenis,
                            company=company,
                            type='in_invoice',
                            prefix='BILL/',
                            suffix=f'/{kode_perusahaan}/{kode_jenis}/%(range_month)s/%(range_year)s',
                        )

                    # 3) generate nomor berdasarkan invoice_date
                    seq_date = move.invoice_date or fields.Date.context_today(move)
                    ctx = dict(self.env.context, ir_sequence_date=seq_date, date=seq_date)
                    nomor_urut = seq.with_context(ctx).next_by_id()
                    
                    _logger.info(f"PUJI")
                    _logger.info(f"Nomor Urut: {nomor_urut}")
                    _logger.info(f"YANTO")
                    
                    move.name = nomor_urut

        # 4) setelah nomor sudah benar, baru post (validasi akan lolos)
        res = super().action_post()

        # 5) sisanya (flag BOP, dst) aman dilakukan setelah post
        for move in self:
            if move.move_type == 'in_invoice':
                self.env['bop.line'].search([('vendor_bill_id', '=', move.id)]).write({
                    'is_created_vendor_bill': True
                })

        return res

                        
    @api.depends('date_sent_to_customer', 'invoice_date', 'invoice_payment_term_id')
    def _compute_aging_invoice_overdue(self):
        if self.is_lms(self.env.company.portfolio_id.name):
            for rec in self:
                # default/fallback
                rec.aging_invoice_overdue = rec.date_sent_to_customer or False

                # butuh base date
                if not rec.date_sent_to_customer:
                    continue

                pt = rec.invoice_payment_term_id
                if not pt:
                    continue

                # Ambil "name" bisa berupa string atau dict 
                raw = pt.name
                if isinstance(raw, dict):
                    # ex: {"en_US": "105"}
                    # prioritaskan en_US
                    val = raw.get('en_US') or next(iter(raw.values()), '')
                else:
                    val = raw or ''

                # Ekstrak angka hari dari val (contoh "105", "Net 30", dsb)
                m = re.search(r'\d+', str(val))
                if not m:
                    continue

                try:
                    days = int(m.group(0))
                except Exception:
                    continue

                rec.aging_invoice_overdue = rec.date_sent_to_customer + timedelta(days=days)
    
    def _reverse_moves(self, default_values_list=None, cancel=False):
        reversals = super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)
        vendor_bills = self.filtered(lambda m: m.move_type == 'in_invoice')
        if vendor_bills:
            lines = self.env['bop.line'].sudo().search([('vendor_bill_id', 'in', vendor_bills.ids)])
            if lines:
                lines.write({
                    'is_created_vendor_bill': False,
                })
                lines.fleet_do_id.write({
                    'remaining_bop_driver_has_been_converted_to_bill': False,
                })

            if 'vendor_bill_id' in self._fields:
                vendor_bills.write({'vendor_bill_id': False})

        return reversals

    @api.onchange('tax_ids')
    def _onchange_tax_ids(self):
        for rec in self:
            rec.invoice_line_ids.tax_ids = rec.tax_ids

    def _compute_can_edit_lines_tax_ids(self):
        for rec in self:
            rec.can_edit_lines_tax_ids = not self.is_lms(rec.env.company.portfolio_id.name)
            
    def _get_sequence_format_param(self, sequence):
        fmt, values = super()._get_sequence_format_param(sequence)

        # Jika default sudah berhasil deteksi month/year, tidak usah diapa-apakan
        if values.get('month') and values.get('year'):
            return fmt, values

        # Pola nomor BILL: BILL/00003/LMKS/TRP/10/2025
        m = re.match(
            r'^BILL/(?P<number>\d{1,9})/(?P<company>[A-Z0-9]+)/(?P<jenis>[A-Z0-9]+)/(?P<month>\d{1,2})/(?P<year>\d{4})$',
            sequence or ''
        )
        if m:
            values['month'] = int(m.group('month'))
            values['year'] = int(m.group('year'))
            values['seq'] = int(m.group('number'))
            return fmt, values

        # Pola nomor INV: INV/00003/VLI/10/2025
        m = re.match(
            r'^INV/(?P<number>\d{1,9})/(?P<company>[A-Z0-9]+)/(?P<month>\d{1,2})/(?P<year>\d{4})$',
            sequence or ''
        )
        if m:
            values['month'] = int(m.group('month'))
            values['year'] = int(m.group('year'))
            values['seq'] = int(m.group('number'))
            return fmt, values

        return fmt, values


    def _sequence_matches_date(self):
        # Dengan parser di atas, validasi default akan mengenali INV dan BILL
        return super()._sequence_matches_date()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        # Filter berdasarkan company yang dipilih user
        domain = domain or []

        # Cek apakah sudah ada filter company_id
        has_company_filter = any(
            term[0] == 'company_id'
            for term in domain
            if isinstance(term, (list, tuple)) and len(term) >= 3
        )

        if not has_company_filter:
            # Tambahkan filter company_ids dari context atau env.companies
            company_ids = self.env.context.get('allowed_company_ids', self.env.companies.ids)
            domain = domain + [('company_id', 'in', company_ids)]

        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid
        )