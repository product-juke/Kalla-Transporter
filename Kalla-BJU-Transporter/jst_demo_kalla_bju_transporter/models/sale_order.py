# -*- coding: utf-8 -*-
from datetime import timedelta, datetime

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

SALE_ORDER_STATE = [
    ('draft', "Quotation"),
    ('sent', "Quotation Sent"),
    ('to_approve', "To Approve"),
    ('approved', "Approved"),
    ('sale', "Sales Order"),
    ('cancel', "Cancelled"),
]
BRANCH_PROJECT = [
    ('lmks', "LMKS"),
    ('ljkt', "LJKT"),
    ('vli', "VLI"),
    ('clm', "CLM"),
    ('bpp', "BPP"),
    ('sby1', "SBY1"),
    ('bpp1', "BPP1"),
    ('mks1', "MKS1"),
    ('mks2', "MKS2"),
    ('lwu', "LWU"),
    ('cabo', "CABO"),
]

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portfolio.view.mixin']

    def _default_company_code(self):
        company = self.env.company
        return str(company.company_code).lower() if company and company.company_code else False
    state = fields.Selection(selection=SALE_ORDER_STATE, string="Status", readonly=True, copy=False, index=True, tracking=3, default='draft')
    branch_project = fields.Selection(
        selection=BRANCH_PROJECT,
        required=True,
        default=_default_company_code,
    )
    access_approval = fields.Boolean(compute='compute_access_approval')
    access_approval_note = fields.Boolean(compute='compute_access_approval')
    approval_date = fields.Date(tracking=True)
    approval_by = fields.Many2one('res.users', tracking=True)
    approval_note = fields.Text('Notes', tracking=True)
    status_negotiation = fields.Selection([('deal', 'Confirmed'), ('not_deal', 'Not Confirmed')], default=False)
    do_ids = fields.Many2many('fleet.do', compute='_compute_related_do')
    do_count = fields.Integer(compute='compute_do_count')
    contract_id = fields.Many2one('create.contract', 'Contract Reference', required=True)
    product_category_id = fields.Many2one('product.category', 'Product Category', readonly="True")
    delivery_category_id = fields.Many2one('delivery.category', 'Delivery Category', readonly="True")
    is_header = fields.Boolean('Header DO')
    is_created_from_contract = fields.Boolean('Created from Contract')
    create_contract_line_id = fields.Many2one('create.contract.line', 'Contract Event')
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=False, change_default=True, index=True,
        tracking=1,
        check_company=True,
        readonly="True"
    )
    partner_invoice_id = fields.Many2one(
        comodel_name='res.partner',
        string="Invoice Address",
        # compute='_compute_partner_invoice_id',
        store=False, readonly=True, required=False, precompute=True,
        check_company=True,
        index='btree_not_null',
    )
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string="Delivery Address",
        # compute='_compute_partner_shipping_id',
        store=False, readonly=True, required=False, precompute=True,
        check_company=True,
        index='btree_not_null')
    integrated = fields.Selection([
        ('half', 'Half Integrated'),
        ('full', 'Fully Integrated'),
        ('one_trip', 'One Trip'),
        ('round_trip', 'Round Trip'),
    ], string="Integration")
    no_surat_jalan = fields.Char(string="No. Surat Jalan", compute="_compute_no_surat_jalan")
    show_surat_jalan = fields.Boolean(compute='_compute_show_surat_jalan', store=True)
    so_reference = fields.Char('SO References')
    product_name = fields.Char(related='product_category_id.name')
    x_id = fields.Integer(related="id")
    contract_invoiced_by = fields.Selection(string='Invoiced by', related='contract_id.invoiced_by', store=True)
    do_reference = fields.Char('DO References')
    do_status = fields.Char(string="DO Status", compute="_compute_do_status")
    company_portfolio = fields.Char(
        string="Company Portfolio",
        compute="_compute_company_portfolio",
        store=True,
        default=lambda self: self.env.company.portfolio_id.name
    )
    detail_order_totals = fields.Monetary(compute='_compute_do_totals', exportable=False)
    has_revision = fields.Boolean('So has_revision')
    is_tam = fields.Boolean(related='partner_id.is_tam')
    total_actual_price = fields.Monetary(
        string="Total Actual Price",
        currency_field='currency_id',
        store=True
    )
    detail_order_total_actual_price = fields.Monetary(
        string="Total Actual Price",
        compute='_compute_detail_order_total_actual_price',
        currency_field='currency_id',
        store=True
    )
    invoiced_by = fields.Selection([('volume', 'Volume'),('tonase', 'Tonase'),('ritase', 'Ritase')], 'Invoiced By', readonly=True, store=True, required=True)
    
    @api.depends('sale_order_option_ids.price_unit_actual', 'sale_order_option_ids.is_selected', 'order_line.actual_price_unit')
    def _compute_detail_order_total_actual_price(self):
        for order in self:
            total_price_actual = 0.0
            selected = order.sale_order_option_ids.filtered(lambda x: x.is_selected)
            invoiced_by = (order.invoiced_by or '').strip().lower()
            if invoiced_by == 'tonase':
                for opt in selected:
                    total_price_actual += (opt.qty_tonase_actual or 0.0) * (opt.price_unit_actual or 0.0)
                    
            if invoiced_by == 'volume':
                for opt in selected:
                    total_price_actual += (opt.qty_kubikasi_actual or 0.0) * (opt.price_unit_actual or 0.0)
                        
            order.detail_order_total_actual_price = total_price_actual
            
            first_line = order.order_line[:1]
            fallback_unit = first_line.actual_price_unit if first_line else 0.0
            
            if len(order.sale_order_option_ids) > 0:
                order.total_actual_price = total_price_actual
                if invoiced_by == 'tonase':
                    for opt in selected:
                        first_line.actual_tonase_non_tam = sum(selected.mapped('qty_tonase_actual'))
                if invoiced_by == 'volume':
                    for opt in selected:
                        first_line.actual_volume_non_tam = sum(selected.mapped('qty_kubikasi_actual'))
            else:
                if invoiced_by == 'tonase':
                    order.total_actual_price = fallback_unit * (first_line.actual_tonase_non_tam or first_line.actual_tonase)
                        
                if invoiced_by == 'volume':
                    order.total_actual_price = fallback_unit * (first_line.actual_volume_non_tam or first_line.actual_volume)

    def _compute_company_portfolio(self):
        for rec in self:
            rec.company_portfolio = rec.env.company.portfolio_id.name or False

    @api.depends('order_line.do_ids.state')
    def _compute_do_status(self):
        for order in self:
            dos = order.order_line.mapped('do_ids')
            if dos:
                order.do_status = dos[0].state
            else:
                order.do_status = False

    @api.depends('show_field')
    def _compute_show_surat_jalan(self):
        for record in self:
            record.show_surat_jalan = record.show_field in ('Transporter', 'VLI', 'Trucking')

    def _compute_no_surat_jalan(self):
        for rec in self:
            surat_jalan_values = rec.order_line.mapped('no_surat_jalan')
            valid_values = [str(val) for val in surat_jalan_values if val]
            rec.no_surat_jalan = ", ".join(valid_values)

    @api.model
    def _generate_fleet_so_name(self, code):
        sequence_code = 'sale.order' + '.' + code
        nomor_urut = self.env['ir.sequence'].next_by_code(sequence_code) or '00000'
        bulan = datetime.today().month
        tahun = datetime.today().year
        kode = code if code else 'LMKS'
        return f'SO/{nomor_urut}/{kode}/{bulan}/{tahun}'

    def _compute_related_do(self):
        for po in self:
            po_line_ids = po.order_line.ids  # Ambil semua PO Line dari PO ini

            if po_line_ids:
                # Cari semua DO yang memiliki PO Line yang sama
                related_dos = self.env["fleet.do"].search([
                    ("po_line_ids", "in", po_line_ids)
                ])
                po.do_ids = related_dos
            else:
                po.do_ids = False

    def compute_access_approval(self):
        for rec in self:
            rec.access_approval = False
            rec.access_approval_note = False
            if rec.opportunity_id:
                if rec.amount_untaxed != rec.opportunity_id.harga_jual:
                    if rec.state == 'approved':
                        rec.access_approval = False
                    else:
                        rec.access_approval = True
            if rec.approval_by == rec.env.user:
                rec.access_approval_note = True

    def compute_do_count(self):
        for rec in self:
            rec.do_count = len(rec.do_ids)

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'approved'}

    # membuat DO dari PO
    def action_create_do(self, multiple=None):
        if self.env.context.get('is_from_bulk_action'):
            multiple = True
        so_record = self.filtered(lambda ol: ol.is_header) if multiple else self
        if not so_record:
            so_order_line = self.order_line.sorted(lambda ol: ol.bop, reverse=True)[0]
            so_record = so_order_line.order_id
        #     raise ValidationError('Belum Memilih Header untuk DO')
        # if len(so_record) > 1:
        #     raise ValidationError('Pilih hanya satu Header saja!')
        category = len(self.order_line.mapped('product_id').mapped('vehicle_category_id')) > 1
        so_line_avail = self.order_line.filtered(lambda ol: not ol.do_id).ids
        if not so_line_avail:
            raise ValidationError('SO Line tidak ada yang bisa dibuat DO')
        if category and not any(self.order_line.mapped('product_id.vehicle_category_id.optional_products')):
            raise ValidationError('DO tidak bisa di buat. Category berbeda-beda')
        if multiple and self.filtered(lambda so: so.state != 'sale'):
            raise ValidationError('DO Tidak Bisa dibuat. Ada SO yang belum di Confirm')

        # vehicle_category = next(iter(self.order_line), False)
        # if vehicle_category:
        #     vehicle_category_id = vehicle_category.vehicle_category_id

        # FIXED: Use .filtered() method instead of calling order_line as function
        vehicle_category_id = self.order_line.filtered(lambda line: line.is_line)[:1].product_id.vehicle_category_id or \
                              self.order_line[:1].product_id.vehicle_category_id
        tonase = sum(self.order_line.mapped('qty_tonase'))
        volume = sum(self.order_line.mapped('qty_kubikasi'))
        unit = sum(self.order_line.mapped('qty_unit'))
        ritase = sum(self.order_line.mapped('qty_ritase'))

        if ritase > 1:
            raise ValidationError('Jumlah Ritase pada DO tidak boleh lebih dari 1.')

        product_detail = []
        for rec in self:
            if rec.contract_id.contract_type in ['transporter', 'trucking']:
                if tonase < vehicle_category_id.min_tonase or tonase > vehicle_category_id.max_tonase:
                    raise ValidationError('Tonase Tidak Sesuai dengan Category di line')
                elif volume < vehicle_category_id.min_kubikasi or volume > vehicle_category_id.max_kubikasi:
                    raise ValidationError('Volume Tidak Sesuai dengan Category di line')
                elif unit < vehicle_category_id.max_unit:
                    raise ValidationError('Jumlah Unit Tidak Sesuai dengan Category di line')

            if rec.order_line.filtered(lambda ol: ol.do_id):
                continue  # Skip if already linked to a DO

            # Prepare product details
            for option_line in rec.sale_order_option_ids:
                product_detail.append(
                    (0, 0, {
                        'product_id': option_line.product_id.id,
                        'product_code': option_line.product_code,
                        'ce_code': option_line.ce_code,
                        'product_description': option_line.name,
                        'unit_price': option_line.price_unit,
                        'qty': option_line.quantity,
                        'uom_id': option_line.uom_id.id,
                    })
                )

            # Define source record
        po_line = [(6, 0, so_line_avail)]
        if not multiple and so_record.order_line.filtered(lambda ol: ol.do_id):
            return

        if so_record:
            if not any(self.order_line.mapped('product_id').mapped('vehicle_category_id').mapped('is_shipment')):
                _logger.info("RORO")
                category_id = self.env['fleet.vehicle.model.category'].search([
                    ('min_tonase', '<=', tonase),
                    ('max_tonase', '>=', tonase),
                    ('min_kubikasi', '<=', volume),
                    ('max_kubikasi', '>=', volume)
                ]) if so_record.product_category_id.name != 'VLI' else vehicle_category_id

                category = so_record.order_line.mapped('product_id.vehicle_category_id')[:1].id
                if category_id:
                    category = category_id[0].id
                if vehicle_category_id.id in category_id.mapped('id'):
                    category = vehicle_category_id.id

                query = '''select fv.id from fleet_vehicle fv 
                left join res_partner rp on fv.driver_id = rp.id
                left join fleet_vehicle_status fvs on fv.last_status_description_id = fvs.id
                where fv.vehicle_status = 'ready'
                and rp.availability = 'Ready'
                and fv.company_id = {company}
                and fvs.name_description = 'Ready for Use'
                and fv.category_id = {category}
                and fv.asset_type = 'asset'
                '''.format(category=category, company=self.company_id.id)
            else:
                _logger.info("RERE")
                category_id = self.env['fleet.vehicle.model.category'].search([('is_shipment', '=', True),
                                                                      ('name', 'ilike', 'shipment')])
                query = '''select fv.id from fleet_vehicle fv 
                left join fleet_vehicle_status fvs on fv.last_status_description_id = fvs.id
                where fv.vehicle_status = 'ready'
                and fv.company_id = {company}
                and fvs.name_description = 'Ready for Use'
                and fv.category_id = {category}
                '''.format(category=category_id[0].id if category_id else so_record.order_line.mapped(
                    'product_id.vehicle_category_id')[:1].id, company=self.company_id.id)
            _logger.info("DEBUG QUERY: %s ..." % query)
            so_record.env.cr.execute(query)
            vehicle_ids = [x[0] for x in self.env.cr.fetchall()]
            _logger.info(f'Query Result Get Fleet Data on Create DO => {vehicle_ids}')
            vehicle_id = self.env['fleet.vehicle'].browse(vehicle_ids)
            so_record.order_line.filtered(lambda cat: cat.product_id.vehicle_category_id and cat.is_line).write({"is_header": True})

            rec = self[0]
            if not rec.branch_project:
                raise ValidationError('Field Branch Project harus diisi sebelum membuat DO')

            bp_value = dict(rec._fields['branch_project'].selection).get(rec.branch_project)
            if not bp_value:
                raise ValidationError('Kode cabang (branch project) tidak ditemukan')

            do_name = rec.env['fleet.do']._generate_fleet_do_name(bp_value)
            if vehicle_id and so_record.delivery_category_id.name != 'Self Drive':
                vehicle = vehicle_id[0].id
                driver = vehicle_id[0].driver_id.id
            elif so_record.delivery_category_id.name == 'Self Drive':
                vehicle = False
                driver_list = self.env['res.partner'].search([('is_driver', '=', True),
                                                        ('availability', '=', 'Ready')])
                if driver_list:
                    driver = driver_list[0].id
                else:
                    raise ValidationError('Tidak menemukan Driver dengan status Ready')
            else:
                vehicle = so_record.order_line.mapped('product_id.vehicle_id')[:1].id
                driver = so_record.order_line.mapped('product_id.vehicle_id')[:1].driver_id.id
            vals = {
                'name': do_name,
                'reference': so_record.id,
                # 'category_id': category_id[0].id if category_id else
                # so_record.order_line.mapped('product_id.vehicle_category_id')[:1].id,
                'category_id': vehicle_category_id.id,
                'vehicle_id': vehicle,
                'driver_id': driver,
                'product_category_id': so_record.product_category_id.id,
                'delivery_category_id': so_record.delivery_category_id.id,
                'date': so_record.date_order,
                'partner_id': so_record.partner_id.id,
                'po_line_ids': po_line,
                'do_product_variant_ids': product_detail,
                'integrated': rec.integrated
            }
            do = so_record.env['fleet.do'].create(vals)

            # create BOP LIST
            longest_lines = do.po_line_ids.filtered(
                lambda l: (l.distance or 0) == max(do.po_line_ids.mapped('distance') or [0])
            )

            bop_list_valls = {
                'fleet_do_id': do.id,
                'is_created_form': 'SO'
            }

            self.env['bop.line'].create(bop_list_valls)

        so_record.filtered(lambda ol: ol.is_header).is_header = False
        if multiple:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Open Record',
                'res_model': 'fleet.do',
                'view_mode': 'form',
                'res_id': do.id if do else False,
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Open Record',
                'res_model': 'fleet.do',
                'view_mode': 'form',
                'res_id': do.id if do else False,
                'target': 'current',
            }

    def action_view_do(self):
        return {
            'name': _('DO'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'fleet.do',
            'domain': [('id', 'in', self.do_ids.ids)],
        }

    def action_request_approval(self):
        self.state = 'to_approve'

    def action_approve(self):
        self.approval_date = fields.Date.today()
        self.approval_by = self.env.user.id
        self.state = 'approved'

    def action_reject(self):
        self.approval_date = fields.Date.today()
        self.approval_by = self.env.user.id
        self.action_cancel()

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        self.status_negotiation = 'deal'
        # for line in self.order_line:
        #     line.vehicle_id.x_studio_due_date = self.date_order + timedelta(days=line.route.sla)
        # return res
        if isinstance(res, dict):
            return res
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}


    def action_cancel(self):
        is_from_revision_wizard = self.env.context.get('is_from_revision_wizard')

        # if self.do_ids and not is_from_revision_wizard:
        #     raise UserError('Tidak bisa dibatalkan karena sudah memiliki minimal 1 Delivery Order terkait.')

        res = super(SaleOrder, self).action_cancel()
        self.status_negotiation = 'not_deal'
        self.state = 'cancel'
        return res

    def action_draft(self):
        res = super(SaleOrder, self).action_draft()
        self.status_negotiation = False
        return res

    # def create(self, vals_list):
    #     res = super(SaleOrder, self).create(vals_list)
    #     # _logger.info(vals_list)
    #     # _logger.info(res)
    #     if isinstance(vals_list, list):
    #         for vals in vals_list:
    #             name = vals.get('name')[:17] + ' ' + \
    #                    self.env['res.partner'].browse(vals.get('partner_id')).name + \
    #                    vals.get('name')[17:]
    #             res.name = name
    #     else:
    #         name = vals_list.get('name')[:17] + ' ' + \
    #                self.env['res.partner'].browse(vals_list.get('partner_id')).name + \
    #                vals_list.get('name')[17:]
    #         res.name = name
    #     return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SaleOrder, self).create(vals_list)
        # _logger.info(vals_list)
        # _logger.info(res)
        if self.is_lms(self.env.company.portfolio_id.name):
            # res.name = self._generate_fleet_so_name(dict(self._fields['branch_project'].selection).get(vals_list[0]['branch_project']))
            for rec, vals in zip(res, vals_list):
                branch_project = rec.branch_project
                branch_project_name = dict(self._fields['branch_project'].selection).get(branch_project)
                rec.name = self._generate_fleet_so_name(branch_project_name)
        return res

    def unlink(self):
        is_from_revision_wizard = self.env.context.get('is_from_revision_wizard')

        for rec in self:
            if rec.do_ids and not is_from_revision_wizard:
                raise UserError('Tidak bisa dihapus karena sudah memiliki minimal 1 Delivery Order terkait.')

            if rec.state not in ("draft", "cancel"):
                raise UserError('Dokumen hanya bisa dihapus jika statusnya "Draft" atau "Cancelled".')

        return super(SaleOrder, self).unlink()


    @api.onchange('product_category_id')
    def _onchange_product_category_id(self):
        """Update analytic distribution ketika product_category_id berubah di form"""
        if self.product_category_id and self.is_lms(self.env.company.portfolio_id.name):
            self._update_order_lines_analytic_distribution()

    def compute_analytic_distribution(self):
        """Update analytic distribution ketika product_category_id berubah di form"""
        if self.product_category_id and self.is_lms(self.env.company.portfolio_id.name):
            self._update_order_lines_analytic_distribution()
            
    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed', 'currency_id', 'sale_order_option_ids.is_selected')
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    def write(self, vals):
        res = super().write(vals)

        if 'product_category_id' in vals and self.is_lms(self.env.company.portfolio_id.name):
            self._update_order_lines_analytic_distribution()

        return res

    def _get_or_create_analytic_account(self, category_name):
        """Get existing analytic account or create new one based on product category name"""
        if not category_name:
            return False

        # Search for existing analytic account
        analytic_account = self.env['account.analytic.account'].search([
            ('name', '=', category_name)
        ], limit=1)

        # Create if doesn't exist
        if not analytic_account:
            # Get the default analytic plan or create one if none exists
            default_plan = self._get_or_create_analytic_plan(category_name)

            analytic_account = self.env['account.analytic.account'].create({
                'name': category_name,
                'code': category_name[:11],  # Use first 10 chars as code
                'plan_id': default_plan.id,  # Set the mandatory plan_id field
            })

        return analytic_account

    def _get_or_create_analytic_plan(self, category_name):
        """Get existing analytic plan or create new one based on category name"""
        # Search for existing analytic plan
        analytic_plan = self.env['account.analytic.plan'].search([
            ('name', '=', category_name)
        ], limit=1)

        # Create if doesn't exist
        if not analytic_plan:
            analytic_plan = self.env['account.analytic.plan'].create({
                'name': category_name,
                'description': f'Analytic plan for {category_name}',
            })

        return analytic_plan

    def _update_order_lines_analytic_distribution(self):
        """Update analytic distribution for all order lines based on product_category_id"""
        if self.product_category_id and self.product_category_id.name:
            analytic_account = self._get_or_create_analytic_account(self.product_category_id.name)
            if analytic_account:
                analytic_distribution = {str(analytic_account.id): 100}
                for line in self.order_line:
                    if line.can_update_analytic_distribution_via_so:
                        line.write({'analytic_distribution': analytic_distribution})
                        
    def action_open_actual_wizard(self):
        print(self.id)
        return {
            'name': "Set Actual Tonase & Volume",
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.actual.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
            }
        }
        
    def action_open_do_select_canceled_so_wizard(self):
        return {
            "name": "Pilih DO & SO Cancel",
            "type": "ir.actions.act_window",
            "res_model": "do.select.canceled.so.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "sale.order",
                "active_id": self.id,
                "active_ids": self.ids,
            },
        }
        
    # @api.onchange('sale_order_option_ids.is_selected', 'sale_order_option_ids.price_unit')
    # def _onchange_option_ids_selected(self):
    #     for order in self:
    #         total = sum(order.sale_order_option_ids.filtered('is_selected').mapped('price_unit') or [0.0])
    #         order.order_line.write({'bop': total})

    @api.depends_context('lang')
    @api.depends('sale_order_option_ids.price_unit', 'sale_order_option_ids.is_selected')
    def _compute_do_totals(self):
        for order in self:
            detail_order = order.sale_order_option_ids.filtered(lambda x: x.is_selected)
            invoiced = order.contract_id.invoiced_by
            if invoiced == 'volume':
                order.detail_order_totals = sum([line.price_unit * line.qty_kubikasi for line in detail_order])
            elif invoiced == 'ritase':
                order.detail_order_totals = sum([line.price_unit * line.qty_ritase for line in detail_order])
            elif invoiced == 'tonase':
                order.detail_order_totals = sum([line.price_unit * line.qty_tonase for line in detail_order])
            else:
                order.detail_order_totals = sum([line.price_unit * line.quantity for line in detail_order])


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'portfolio.view.mixin']

    vehicle_id = fields.Many2one('fleet.vehicle', related='product_id.vehicle_id')
    route = fields.Many2one('fleet.route')
    # origin = fields.Many2one('x_master_origin')
    # destination = fields.Many2one('x_master_destination')
    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
    attachment = fields.Binary(string='Attachment', attachment=True)
    file_name = fields.Char()
    no_surat_jalan = fields.Char()
    do_id = fields.Many2one('fleet.do', 'Delivery Order')
    is_handling_type = fields.Boolean('HANDLING')
    is_line = fields.Boolean('LINE')
    id_contract = fields.Char('CE. CODE')
    distance = fields.Integer('DISTANCE (KM)')
    sla = fields.Integer('SLA DELIVERY (Day)')
    description = fields.Char()
    qty_tonase = fields.Float('TONASE (Ton)', compute='_compute_totals_from_options', store=True, readonly=False)
    qty_kubikasi = fields.Float('VOLUME (Kubikasi)', compute='_compute_totals_from_options', store=True, readonly=False)
    qty_unit = fields.Float('UNIT/PCS')
    qty_dus = fields.Float('DUS/BOX')
    qty_ritase = fields.Float('RITASE', compute='_compute_totals_from_options', store=True, readonly=False)
    contract_qty_ritase = fields.Float()
    qty_target_ritase = fields.Float('TARGET RITASE (Trucking)')
    bop = fields.Monetary('BOP', currency_field='currency_id')
    # price_unit = fields.Monetary(string="PRICE", compute='_compute_totals_from_options', store=True, currency_field='currency_id')
    active = fields.Boolean('STATUS PRICE', default=True)
    is_header = fields.Boolean('Header DO', default=False)
    can_update_analytic_distribution_via_so = fields.Boolean(default=True)
    do_ids = fields.Many2many(
        'fleet.do', 'do_po_line_rel', 'po_line_id', 'do_id', string='Fleet DOs'
    )
    show_surat_jalan = fields.Boolean(compute='_compute_show_surat_jalan', store=True)
    customer_id = fields.Many2one('res.partner', related='order_id.partner_id')
    actual_tonase = fields.Float(string="Actual Tonase", store=True)
    actual_volume = fields.Float(string="Actual Volume", store=True)
    so_reference = fields.Char('So Refence')
    actual_price_unit = fields.Float(string="Actual Price", store=True, readonly=False)
    product_category_name = fields.Char(related='do_id.product_category_id.name')
    actual_tonase_non_tam = fields.Float(string="Actual Tonase", store=True, readonly=False)
    actual_volume_non_tam = fields.Float(string="Actual Volume", store=True, readonly=False)
    
    @api.onchange('actual_tonase_non_tam', 'actual_volume_non_tam')
    def _onchange_actuals(self):
        for rec in self:
            rec.actual_tonase = rec.actual_tonase_non_tam
            rec.actual_volume = rec.actual_volume_non_tam
        
    @api.depends_context('lang')
    @api.depends(
        # TRANSPORTER (LMKS) triggers
        'order_id.sale_order_option_ids.is_selected',
        'order_id.sale_order_option_ids.price_unit',
        'order_id.sale_order_option_ids.qty_tonase',
        'order_id.sale_order_option_ids.qty_kubikasi',
        'order_id.sale_order_option_ids.qty_ritase',
        'order_id.sale_order_option_ids.qty_tonase_actual',
        'order_id.sale_order_option_ids.qty_kubikasi_actual',
        'order_id.sale_order_option_ids.price_unit_actual',
        'order_id.invoiced_by',

        # VLI triggers
        'order_id.sale_order_option_ids.quantity',

        # Switcher
        'order_id.branch_project',
    )
    def _compute_totals_from_options(self):
        """
        - Jika branch_project == 'lmks'  -> hitung berdasarkan invoiced_by (tonase/volume/ritase) + actual.
        - Jika branch_project == 'vli'   -> hitung Σ(qty * price_unit) dari opsi terpilih + total qty_unit.
        - Selain itu, nolkan semua nilai agar tidak kebawa.
        """
        for line in self:
            order = line.order_id
            if not order:
                # Nolkan semua kalau tidak ada order
                line.update({
                    'price_unit': 0.0,
                    'qty_tonase': 0.0,
                    'qty_kubikasi': 0.0,
                    'qty_ritase': 0.0,
                    'actual_tonase': 0.0,
                    'actual_volume': 0.0,
                    'actual_price_unit': 0.0,
                    'qty_unit': 0.0,  # untuk VLI
                })
                continue

            branch = (order.branch_project or '').strip().lower()

            if branch == 'lmks':
                selected = order.sale_order_option_ids.filtered('is_selected')

                total_price = 0.0
                total_price_actual = 0.0

                invoiced_by = (order.invoiced_by or '').strip().lower()

                if invoiced_by == 'tonase':
                    for opt in selected:
                        total_price += (opt.qty_tonase or 0.0) * (opt.price_unit or 0.0)
                        total_price_actual += (opt.qty_tonase_actual or 0.0) * (opt.price_unit_actual or 0.0)

                    line.qty_tonase = sum(selected.mapped('qty_tonase'))
                    line.actual_tonase = sum(selected.mapped('qty_tonase_actual'))
                    line.qty_kubikasi = 0.0
                    line.qty_ritase = 0.0
                    line.actual_volume = 0.0

                elif invoiced_by == 'volume':
                    for opt in selected:
                        total_price += (opt.qty_kubikasi or 0.0) * (opt.price_unit or 0.0)
                        total_price_actual += (opt.qty_kubikasi_actual or 0.0) * (opt.price_unit_actual or 0.0)

                    line.qty_kubikasi = sum(selected.mapped('qty_kubikasi'))
                    line.actual_volume = sum(selected.mapped('qty_kubikasi_actual'))
                    line.qty_tonase = 0.0
                    line.qty_ritase = 0.0
                    line.actual_tonase = 0.0

                elif invoiced_by == 'ritase':
                    for opt in selected:
                        total_price += (opt.qty_ritase or 0.0) * (opt.price_unit or 0.0)
                        # kalau ada actual ritase field, pakai di sini juga
                        total_price_actual += (opt.qty_ritase or 0.0) * (opt.price_unit_actual or 0.0)

                    line.qty_ritase = line.contract_qty_ritase
                    line.qty_tonase = 0.0
                    line.qty_kubikasi = 0.0
                    line.actual_tonase = 0.0
                    line.actual_volume = 0.0

                else:
                    total_price = 0.0
                    total_price_actual = 0.0
                    line.qty_tonase = line.qty_kubikasi = line.qty_ritase = 0.0
                    line.actual_tonase = line.actual_volume = 0.0

                # simpan hasil
                line.price_unit = total_price
                line.actual_price_unit = total_price_actual


            elif branch == 'vli':
                # ============ VLI ============
                selected = order.sale_order_option_ids.filtered('is_selected')
                if selected:
                    total_quantity = sum(selected.mapped('quantity'))
                    # Σ(quantity * price_unit)
                    price_sum = 0.0
                    for opt in selected:
                        price_sum += (opt.quantity or 0.0) * (opt.price_unit or 0.0)
                else:
                    total_quantity = 0.0
                    price_sum = 0.0

                line.update({
                    'qty_unit': total_quantity,
                    'price_unit': price_sum,

                    # pastikan field transporter ikut nol ketika VLI
                    'qty_tonase': 0.0,
                    'qty_kubikasi': 0.0,
                    'qty_ritase': 0.0,
                    'actual_tonase': 0.0,
                    'actual_volume': 0.0,
                    'actual_price_unit': 0.0,
                })

            else:
                # ============ default/other branches ============
                line.update({
                    'price_unit': 0.0,
                    'qty_unit': 0.0,
                    'qty_tonase': 0.0,
                    'qty_kubikasi': 0.0,
                    'qty_ritase': 0.0,
                    'actual_tonase': 0.0,
                    'actual_volume': 0.0,
                    'actual_price_unit': 0.0,
                })


    @api.depends('show_field')
    def _compute_show_surat_jalan(self):
        for record in self:
            record.show_surat_jalan = record.show_field in ('Transporter', 'VLI', 'Trucking')

    # @api.model
    # def create(self, vals):
    #     """Override create to set analytic distribution based on product category"""
        # res = super(SaleOrderLine, self).create(vals)
        # res._set_analytic_distribution_from_category()
        # return res

    def _set_analytic_distribution_from_category(self):
        """Set analytic distribution based on sale order's product category"""
        for line in self:
            if line.order_id.product_category_id and line.order_id.product_category_id.name:
                analytic_account = line.order_id._get_or_create_analytic_account(
                    line.order_id.product_category_id.name
                )
                if analytic_account:
                    line.analytic_distribution = {str(analytic_account.id): 100}

    @api.constrains('is_header', 'do_ids')
    def _check_single_header_per_do(self):
        is_from_revision_wizard = self.env.context.get('is_from_revision_wizard')

        """Pastikan per DO tidak ada lebih dari 1 line yang is_header=True."""
        for line in self.filtered('is_header'):
            for do in line.do_ids:
                # cari line lain (selain line ini) yg juga header pada DO yg sama
                dup_count = self.search_count([
                    ('id', '!=', line.id),
                    ('is_header', '=', True),
                    ('do_ids', 'in', do.id),
                ])
                if dup_count and not is_from_revision_wizard:
                    raise ValidationError(_("DO '%s' sudah punya Header. Hanya boleh satu.") % (do.display_name,))

    def _unset_other_headers_in_same_dos(self):
        """Matikan header lain pada DO yang sama dengan baris self (untuk line yang header=True)."""
        for line in self.filtered('is_header'):
            if not line.do_ids:
                continue
            others = self.search([
                ('id', '!=', line.id),
                ('is_header', '=', True),
                ('do_ids', 'in', line.do_ids.ids),
            ])
            if others:
                # nonaktifkan semua header lain di DO yang sama
                others.write({'is_header': False})

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        if vals.get('is_header'):
            rec._unset_other_headers_in_same_dos()
        return rec

    def write(self, vals):
        """Override write method to handle header updates and no_surat_jalan changes."""
        res = super().write(vals)

        # Debug log untuk tracking perubahan no_surat_jalan
        # print("'no_surat_jalan' in vals: ", 'no_surat_jalan' in vals)

        # Handle header updates - pastikan hanya satu header per DOS
        if self._should_update_headers(vals):
            self._unset_other_headers_in_same_dos()

        # Update no_surat_jalan jika ada perubahan
        if 'no_surat_jalan' in vals:
            self.update_no_surat_jalan()

        return res

    def _should_update_headers(self, vals):
        """Check if header updates are needed."""
        return 'is_header' in vals and any(self.mapped('is_header'))

    def update_no_surat_jalan(self):
        """Update no_surat_jalan across related records (BOP lines and invoice lines)."""
        # Collect semua no_surat_jalan yang ada
        no_surat_jalan_list = self._collect_no_surat_jalan()

        # Update related records untuk setiap record yang memiliki no_surat_jalan
        for record in self.filtered(lambda r: r.no_surat_jalan and r.do_id):
            self._update_related_records(record, no_surat_jalan_list)

    def _collect_no_surat_jalan(self):
        """Collect all no_surat_jalan values from current recordset."""
        return [rec.no_surat_jalan for rec in self if rec.no_surat_jalan]

    def _update_related_records(self, record, no_surat_jalan_list):
        """Update BOP lines and invoice lines with consolidated no_surat_jalan."""
        consolidated_no_sj = ', '.join(no_surat_jalan_list)

        # Update BOP lines
        self._update_bop_lines(record.do_id.id, consolidated_no_sj)

        # Update invoice lines melalui sale order line relation
        self._update_invoice_lines_via_sale_order(record.id, consolidated_no_sj)

    def _update_bop_lines(self, do_id, no_surat_jalan):
        """Update BOP lines and their related vendor bill lines."""
        bop_lines = self.env['bop.line'].search([('fleet_do_id', '=', do_id)])

        if not bop_lines:
            return

        # Update BOP lines
        bop_lines.sudo().write({'no_surat_jalan': no_surat_jalan})

        # Update vendor bill lines
        for bop_line in bop_lines:
            self._update_vendor_bill_lines(bop_line, no_surat_jalan)

    def _update_vendor_bill_lines(self, bop_line, no_surat_jalan):
        """Update vendor bill lines if they exist."""
        if bop_line.vendor_bill_id and bop_line.vendor_bill_id.invoice_line_ids:
            bop_line.vendor_bill_id.invoice_line_ids.write({
                'no_surat_jalan': no_surat_jalan
            })

        purchase = self.env['purchase.order'].search([
            ('fleet_do_id', '=', bop_line.fleet_do_id.id),
        ], limit=1) # 1 DO hanya punya 1 PO

        bills = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('invoice_origin', 'in', str(purchase.name).split(', ')),
        ])

        if bills:
            for bill in bills:
                bill.invoice_line_ids.write({
                    'no_surat_jalan': no_surat_jalan
                })


    def _update_invoice_lines_via_sale_order(self, order_line_id, no_surat_jalan):
        """Update invoice lines through sale order line relation using direct query."""
        query = """
            SELECT solir.invoice_line_id
            FROM sale_order_line_invoice_rel solir
            WHERE solir.order_line_id = %s
        """

        self.env.cr.execute(query, (order_line_id,))
        invoice_line_ids = [row['invoice_line_id'] for row in self.env.cr.dictfetchall()]

        if invoice_line_ids:
            invoice_lines = self.env['account.move.line'].browse(invoice_line_ids)
            invoice_lines.write({'no_surat_jalan': no_surat_jalan})

    def unlink(self):
        order = self.mapped('order_id')
        if order.is_fms(self.env.company.portfolio_id.name):
            return super().unlink()
        line = order.order_line
        armada = line.filtered(lambda ol: ol.is_line)
        bop = sum((line - self).mapped('bop'))
        is_vli = bool(order.product_category_id.name == 'VLI')
        is_selfdrive = bool(order.delivery_category_id) and order.delivery_category_id.name == 'Self Drive'
        # True if any line’s product category is shipment
        has_shipment = any(armada.mapped('product_id.vehicle_category_id.is_shipment'))
        for rec in self:
            if is_vli and rec.id_contract == False and self.is_lms(self.env.company.portfolio_id.name):
                armada_lines = rec.order_id.order_line.filtered(
                    lambda x: x.id_contract != False
                )
                print('armada ', armada_lines)
                if len(armada_lines) > 0:
                    armada_lines[0].qty_unit -= 1

        if not(armada.bop == bop and (has_shipment or is_selfdrive or is_vli)):
            return super().unlink()
        else:
            bop = self.env['fleet.bop'].search(
                [
                    ("customer", "=", order.partner_id.id),
                    ("origin_id", "=", armada.origin_id.id),
                    ("destination_id", "=", armada.destination_id.id),
                    ("category_id", "=", armada.product_id.vehicle_category_id.id),
                ],
                limit=1,
            ).total_bop
            armada.bop = bop
            return super().unlink()

    def action_create_do(self, multiple=None):
        if self.env.context.get('is_from_bulk_action'):
            multiple = True
        FleetDo = self.env['fleet.do']
        lines_to_process = self.filtered(lambda l: not l.do_id)
        if not lines_to_process:
            raise ValidationError('Tidak ada line yang bisa dibuat DO (semua sudah terhubung DO).')
        header_line = lines_to_process.filtered(lambda l: l.is_header) if multiple else lines_to_process[:1]
        if multiple and not header_line:
            header_line = lines_to_process.sorted(lambda ol: ol.bop or 0, reverse=True)[:1]
        header_so = header_line.order_id


        if multiple:
            not_confirmed = lines_to_process.mapped('order_id').filtered(lambda so: so.state != 'sale')
            if not_confirmed:
                raise ValidationError('DO Tidak Bisa dibuat. Ada SO yang belum di Confirm.')

        selected_categories = lines_to_process.mapped('product_id.vehicle_category_id')
        category_mixed = len(selected_categories) > 1
        if category_mixed and not any(selected_categories.mapped('optional_products')):
            raise ValidationError('DO tidak bisa di buat. Category berbeda-beda')

        vehicle_category_id = (
                lines_to_process.filtered(lambda line: line.is_line)[:1].product_id.vehicle_category_id
                or lines_to_process[:1].product_id.vehicle_category_id
        )
        tonase = sum(lines_to_process.mapped('qty_tonase'))
        volume = sum(lines_to_process.mapped('qty_kubikasi'))
        unit = sum(lines_to_process.mapped('qty_unit'))
        ritase = sum(self.order_line.mapped('qty_ritase'))

        if ritase > 1:
            raise ValidationError('Jumlah Ritase pada DO tidak boleh lebih dari 1.')

        if header_so.contract_id.contract_type in ['transporter', 'trucking']:
            if tonase < vehicle_category_id.min_tonase or tonase > vehicle_category_id.max_tonase:
                raise ValidationError('Tonase Tidak Sesuai dengan Category di line')
            if volume < vehicle_category_id.min_kubikasi or volume > vehicle_category_id.max_kubikasi:
                raise ValidationError('Volume Tidak Sesuai dengan Category di line')
            if unit < vehicle_category_id.max_unit:
                raise ValidationError('Jumlah Unit Tidak Sesuai dengan Category di line')
        is_any_shipment = any(selected_categories.mapped('is_shipment'))
        if not is_any_shipment:
            if header_so.product_category_id.name != 'VLI':
                category_id = self.env['fleet.vehicle.model.category'].search([
                    ('min_tonase', '<=', tonase),
                    ('max_tonase', '>=', tonase),
                    ('min_kubikasi', '<=', volume),
                    ('max_kubikasi', '>=', volume),
                ])
            else:
                category_id = vehicle_category_id

            query = '''
                select fv.id from fleet_vehicle fv
                left join res_partner rp on fv.driver_id = rp.id
                left join fleet_vehicle_status fvs on fv.last_status_description_id = fvs.id
                where fv.vehicle_status = 'ready'
                  and rp.availability = 'Ready'
                  and fv.company_id = {company}
                  and fvs.name_description = 'Ready for Use'
                  and fv.category_id = {category}
                  and fv.asset_type = 'asset'
            '''.format(
                company=header_so.company_id.id,
                category=(
                    category_id[0].id if category_id else lines_to_process.mapped('product_id.vehicle_category_id')[
                                                          :1].id)
            )
        else:
            category_id = self.env['fleet.vehicle.model.category'].search([
                ('is_shipment', '=', True),
                ('name', 'ilike', 'shipment'),
            ])
            query = '''
                select fv.id from fleet_vehicle fv
                left join fleet_vehicle_status fvs on fv.last_status_description_id = fvs.id
                where fv.vehicle_status = 'ready'
                  and fv.company_id = {company}
                  and fvs.name_description = 'Ready for Use'
                  and fv.category_id = {category}
                  and fv.asset_type = 'asset'
            '''.format(
                company=header_so.company_id.id,
                category=(
                    category_id[0].id if category_id else lines_to_process.mapped('product_id.vehicle_category_id')[
                                                          :1].id)
            )

        self.env.cr.execute(query)
        vehicle_ids = [x[0] for x in self.env.cr.fetchall()]
        vehicle_rec = self.env['fleet.vehicle'].browse(vehicle_ids)
        if not header_so.branch_project:
            raise ValidationError('Field Branch Project harus diisi sebelum membuat DO')
        bp_value = dict(header_so._fields['branch_project'].selection).get(header_so.branch_project)
        if not bp_value:
            raise ValidationError('Kode cabang (branch project) tidak ditemukan')
        do_name = self.env['fleet.do']._generate_fleet_do_name(bp_value)
        if vehicle_rec and header_so.delivery_category_id.name != 'Self Drive':
            vehicle = vehicle_rec[0].id
            driver = vehicle_rec[0].driver_id.id
        elif header_so.delivery_category_id.name == 'Self Drive':
            vehicle = False
            driver_list = self.env['res.partner'].search([('is_driver', '=', True), ('availability', '=', 'Ready')],
                                                         limit=1)
            if not driver_list:
                raise ValidationError('Tidak menemukan Driver dengan status Ready')
            driver = driver_list.id
        else:
            vehicle = lines_to_process.mapped('product_id.vehicle_id')[:1].id
            driver = lines_to_process.mapped('product_id.vehicle_id')[:1].driver_id.id
        product_detail = []
        if not header_so.order_line.filtered(lambda ol: ol.do_id):
            for opt in header_so.sale_order_option_ids:
                product_detail.append((0, 0, {
                    'order_id': header_so.id,
                    'product_id': opt.product_id.id,
                    'product_code': opt.product_code,
                    'ce_code': opt.ce_code,
                    'product_description': opt.name,
                    'unit_price': opt.price_unit,
                    'qty': opt.quantity,
                    'uom_id': opt.uom_id.id,
                }))
        vals = {
            'name': do_name,
            'reference': header_so.id,  # DO refer ke SO header
            'category_id': vehicle_category_id.id,
            'vehicle_id': vehicle,
            'driver_id': driver,
            'product_category_id': header_so.product_category_id.id,
            'delivery_category_id': header_so.delivery_category_id.id,
            'date': header_so.date_order,
            'partner_id': header_so.partner_id.id,
            'po_line_ids': [(6, 0, lines_to_process.ids)],
            'do_product_variant_ids': product_detail,
            'integrated': header_so.integrated,
        }
        do = FleetDo.create(vals)
        self.env['bop.line'].create({
            'fleet_do_id': do.id,
            'is_created_form': 'SO',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Open Record',
            'res_model': 'fleet.do',
            'view_mode': 'form',
            'res_id': do.id if do else False,
            'target': 'current',
        }


class SaleOrderOption(models.Model):
    _name = 'sale.order.option'
    _inherit = ['sale.order.option', 'portfolio.view.mixin']
    _description = "Sale Options"
    _order = 'sequence, id'

    product_code = fields.Char('PRODUCT CODE')
    # sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    # ce_code = fields.Char('CE. CODE', related='sale_line_id.id_contract', store=True)
    ce_code = fields.Char('CE. CODE')
    qty_tonase = fields.Float('TONASE (Ton)')
    qty_kubikasi = fields.Float('VOLUME (Kubikasi)')
    qty_ritase = fields.Float('RITASE')
    product_category_name = fields.Char(related='order_id.product_category_id.name')
    route_category_id = fields.Many2one('product.attribute', 'Route Category')
    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
    is_selected = fields.Boolean(string="Selected", default=False)
    qty_tonase_actual = fields.Float(string="Actual Tonase")
    qty_kubikasi_actual = fields.Float(string="Actual Volume")
    price_unit_actual = fields.Float(string="Actual Price")
    attachment = fields.Binary(string='Attachment', attachment=True)
    file_name = fields.Char()
    no_surat_jalan = fields.Char()
    
    @api.onchange('is_selected')
    def _onchange_actuals(self):
        for rec in self:
            order = rec.order_id
            branch = (order.branch_project or '').strip().lower()
            invoiced_by = (order.invoiced_by or '').strip().lower()

            if branch != 'lmks':
                continue
                
            if rec.is_selected:
                if invoiced_by == 'tonase':
                    rec.qty_tonase_actual = rec.qty_tonase
                    rec.price_unit_actual = rec.price_unit
                    rec.qty_kubikasi_actual = 0.0
                elif invoiced_by == 'volume':
                    rec.qty_kubikasi_actual = rec.qty_kubikasi
                    rec.price_unit_actual = rec.price_unit
                    rec.qty_tonase_actual = 0.0
            else:
                rec.qty_tonase_actual = 0.0
                rec.qty_kubikasi_actual = 0.0
                rec.price_unit_actual = 0.0
    
    def unlink(self):
        locked = self.filtered('is_selected')
        if locked:
            names = "\n- " + "\n- ".join(locked.mapped(lambda r: r.display_name or f"ID {r.id}"))
            raise UserError(_("Tidak bisa menghapus baris opsi yang sedang dipilih (is_selected = True):%s\n"
                              "Silakan uncheck dulu lalu hapus.") % names)
        return super().unlink()

    def _get_values_to_add_to_order(self):
        res = super(SaleOrderOption, self)._get_values_to_add_to_order()
        order = self.order_id
        if not order or order.is_fms(self.env.company.portfolio_id.name):
            return res

        line = order.order_line
        armada = line.filtered(lambda ol: ol.is_line)

        # flags from the order
        has_options = bool(order.sale_order_option_ids)
        is_selfdrive = bool(order.delivery_category_id) and order.delivery_category_id.name == 'Self Drive'
        # True if any line’s product category is shipment
        has_shipment = any(line.mapped('product_id.vehicle_category_id.is_shipment'))
        nilai_bop_product = 0

        # Truth-table gate:
        # proceed only if options AND (selfdrive OR shipment)
        if not (has_options and (is_selfdrive or has_shipment)):
            return res
        if armada.bop > 0:
            nilai_bop_product = armada.bop * self.quantity
            line.bop = 0
        if has_shipment:
            bop = self.product_id.standard_price
            nilai_bop_product = bop * self.quantity
        elif is_selfdrive:
            bop = self.env['fleet.bop'].search(
                [
                    ("customer", "=", order.partner_id.id),
                    ("origin_id", "=", armada.origin_id.id),
                    ("destination_id", "=", armada.destination_id.id),
                    ("category_id", "=", self.product_id.vehicle_category_id.id),
                ],
                limit=1,
            ).total_bop
            nilai_bop_product = bop * self.quantity
        updated_res = {
            'id_contract': self.ce_code,
            'bop': nilai_bop_product
        }
        res.update(updated_res)
        return res
    
    def add_option_to_order(self):
        self.ensure_one()
        sale_order = self.order_id
        is_vli = bool(sale_order.product_category_id.name == 'VLI')
        if not sale_order._can_be_edited_on_portal():
            raise UserError(_('You cannot add options to a confirmed order.'))
        
        product_lines = sale_order.order_line.filtered(lambda l: not l.display_type and l.product_id)
        if product_lines:
            first_line = product_lines.sorted(lambda l: (l.sequence, l.id))[0]
            base_category = getattr(first_line.product_id, 'vehicle_category_id', False)
            max_unit = getattr(base_category, 'max_unit', 0) or 0

            if base_category and max_unit > 0:
                additional_count = len(product_lines) - 1
                print(additional_count, product_lines, max_unit)
                if additional_count >= max_unit:
                    raise UserError(_(
                        "Tidak dapat menambah baris. Kategori %(cat)s sudah mencapai batas maksimal tambahan: %(max)d.",
                    ) % {
                        'cat': base_category.display_name if hasattr(base_category, 'display_name') else base_category.name,
                        'max': max_unit,
                    })

        # === LANJUTKAN PROSES NORMAL BUAT LINE BARU ===
        values = self._get_values_to_add_to_order()
        values['description'] = self.name
        if sale_order.partner_id.is_tam:
            # values['qty_unit'] = self.quantity
            values['qty_ritase'] = self.qty_ritase
            values['qty_kubikasi'] = self.qty_kubikasi
        order_line = self.env['sale.order.line'].create(values)

        self.write({'line_id': order_line.id})
        if sale_order:
            # panggilan bawaan modul (TaxCloud)
            sale_order.add_option_to_order_with_taxcloud()

        if is_vli and self.is_lms(self.env.company.portfolio_id.name):
            armada_lines = self.order_id.order_line.filtered(
                lambda x: x.id_contract != False
            )
            if len(armada_lines) > 0:
                armada_lines[0].qty_unit += 1

        return order_line

class SaleOrderActualWizard(models.TransientModel):
    _name = "sale.order.actual.wizard"
    _description = "Wizard Update Actual Tonase & Volume"

    actual_tonase = fields.Float(string="Actual Tonase", required=True)
    actual_volume = fields.Float(string="Actual Volume", required=True)

    def action_submit(self):
        """Update actual_tonase & actual_volume ke sale.order.line"""
        active_id = self.env.context.get("active_id")
        print(active_id)
        sale = self.env['sale.order'].browse(active_id)
        print(sale)
        for line in sale.order_line:
            line.actual_tonase = self.actual_tonase
            line.actual_volume = self.actual_volume
        return {'type': 'ir.actions.act_window_close'}
    
class DoSelectCanceledSoWizard(models.TransientModel):
    _name = "do.select.canceled.so.wizard"
    _description = "Pilih DO yang punya SO Cancel, lalu pilih SO-nya"
    
    available_do_ids = fields.Many2many(
        "fleet.do", compute="_compute_available_do_ids", string="Available DOs"
    )

    fleet_do_id = fields.Many2one(
        "fleet.do",
        string="Delivery Order",
        required=True,
        domain="[('id', 'in', available_do_ids)]",
    )

    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Canceled SO(s)",
        domain="[('id', 'in', available_so_ids)]",
    )
    available_so_ids = fields.Many2many(
        "sale.order", compute="_compute_available_so_ids", string="Available SOs"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        SaleLine = self.env["sale.order.line"]
        do_field = 'do_id'
        grouped = SaleLine.read_group(
            domain=[("order_id.state", "=", "cancel"), (do_field, "!=", False)],
            fields=[do_field],
            groupby=[do_field],
            lazy=False,
        )
        
        do_ids = [g[do_field][0] for g in grouped if g.get(do_field)]
        res["available_do_ids"] = [(6, 0, do_ids)]
        _logger.info("Wizard available DOs (SO cancel): %s", do_ids)
        return res

    @api.onchange("fleet_do_id")
    def _compute_available_so_ids(self):
        SaleLine = self.env["sale.order.line"]
        for w in self:
            if not w.fleet_do_id:
                w.available_so_ids = [(5, 0, 0)]
                continue
            grouped = SaleLine.read_group(
                domain=[
                    ("do_id", "=", w.fleet_do_id.id),
                    ("order_id.state", "=", "cancel"),
                ],
                fields=["order_id"],
                groupby=["order_id"],
                lazy=False,
            )
            so_ids = [g["order_id"][0] for g in grouped if g.get("order_id")]
            w.available_so_ids = [(6, 0, so_ids)]

    def action_submit(self):
        self.ensure_one()

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        
        if active_model != 'sale.order' or not active_ids:
            raise UserError(_("Buka wizard ini dari form Sales Order yang ingin kamu update."))

        do = self.fleet_do_id
        if not do:
            raise UserError(_("Silakan pilih Delivery Order dulu."))

        so_names = ", ".join(self.sale_order_ids.mapped('name')) if self.sale_order_ids else ""

        SaleLine = self.env['sale.order.line']
        do_field = 'do_id'
        lines = SaleLine.search([('order_id', 'in', active_ids)])

        vals = {do_field: do.id}
        if 'so_reference' in SaleLine._fields:
            vals['so_reference'] = so_names

        if lines:
            lines.write(vals)
            
        FleetDo = self.env['fleet.do']
        m2m_field = None
        if 'po_line_ids' in FleetDo._fields:
            m2m_field = 'po_line_ids'
        elif 'sale_order_line_ids' in FleetDo._fields:
            m2m_field = 'sale_order_line_ids'

        if m2m_field and lines:
            print(do.id)
            canceled_lines = self.env['sale.order.line'].search([
                ('do_id', '=', do.id),
                ('order_id.state', '=', 'cancel'),
            ])
            valid_lines    = lines - canceled_lines

            promote_new_header = False
            if canceled_lines and 'is_header' in canceled_lines._fields:
                promote_new_header = bool(canceled_lines.filtered('is_header'))

            if canceled_lines:
                if 'is_header' in canceled_lines._fields:
                    canceled_lines.write({'is_header': False})
                do[m2m_field] -= canceled_lines

            if valid_lines:
                do[m2m_field] |= valid_lines 

            if promote_new_header and valid_lines and 'is_header' in valid_lines._fields:
                header_line = self.env['sale.order.line'].search(
                    [('id', 'in', valid_lines.ids),('bop', '!=', False),],
                    order='bop desc',
                    limit=1
                )
                header_line.write({'is_header': True})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Order'),
            'res_model': 'fleet.do',
            'res_id': do.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
    @api.onchange("sale_order_ids")
    def _onchange_sale_order_ids(self):
        for w in self:
            if len(w.sale_order_ids) > 1:
                last = w.sale_order_ids[-1]
                w.sale_order_ids = [(6, 0, [last.id])]
                return {
                    "warning": {
                        "title": "Maksimal 1 SO",
                        "message": "Hanya boleh memilih satu Sales Order.",
                    }
                }


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        res = super(SaleAdvancePaymentInv, self).create_invoices()
        for rec in self:
            sales_order = rec.sale_order_ids
            invoice = sales_order.invoice_ids
            date = sorted(sales_order.do_ids.mapped('date'))

            invoice.write({
                'periode_rekapan': date[0].strftime('%d %B %Y') + '-' + date[-1].strftime('%d %B %Y'),
            })
            for line in invoice.line_ids:
                so = line.sale_line_ids.mapped('order_id')
                line.write({
                    'sodo_reference': "-".join(so.mapped('name')) + "-" + "-".join(so.mapped('do_ids.name')),
                    'geofence_unloading': "-".join(so.mapped('do_ids.geofence_unloading_id.display_name'))
                })
        return res
