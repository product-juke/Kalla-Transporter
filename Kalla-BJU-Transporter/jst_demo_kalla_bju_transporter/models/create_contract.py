from odoo import fields, models, api, _
import logging
from datetime import datetime, time

from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.osv import expression
import json

_logger = logging.getLogger(__name__)

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

class CreateContract(models.Model):
    _name = 'create.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # name = fields.Char()
    name = fields.Char(
        string='Contract Number',
        copy=False,
        readonly=True
    )
    partner_id = fields.Many2one('res.partner')
    customer_product_ids = fields.Many2many('product.customer', relation="contract_product_rel", column1="customer_id",
                                            column2="product_customer_id",
                                            string='Product Customer', tracking=True)
    # contract_no = fields.Char('Contract No')
    contract_type = fields.Selection([('vehicle_logistic', 'Vehicle Logistic'), ('transporter', 'Transporter'),('trucking', 'Trucking')],
                                     'Contract Type')
    # phone = fields.Char()
    # email = fields.Char()
    phone = fields.Char(compute='_compute_partner_details', store=True)
    email = fields.Char(compute='_compute_partner_details', store=True)

    responsible_id = fields.Many2one('res.users')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.user.company_id.id,
        required=True
    )
    company_ids = fields.Many2many(
        'res.company',
        'contract_company_rel',  # nama tabel relasi
        'contract_id',  # kolom foreign key ke contract
        'company_id',  # kolom foreign key ke company
        string='Companies'
    )
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    crm_id = fields.Many2one('crm.lead')
    line_ids = fields.One2many(comodel_name='create.contract.line', inverse_name='contract_id')
    inactive_line_ids = fields.One2many(comodel_name='create.contract.line.archive', inverse_name='contract_id')
    product_detail_ids = fields.One2many(comodel_name='detail.product.variant', inverse_name='contract_id')
    state = fields.Selection([('new', 'New'), ('running', 'Running'), ('expired', 'Expired'), ('close', 'Closed')],
                             default='new')
    working_day_ids = fields.Many2many('dayofweek',relation="dayofweek_rel",column1="customer_id", column2="dayofweek_id", string='Working Time', tracking=True)
    insurance_by = fields.Selection([('0', 'By Customer'), ('1', 'By BJU')], 'Asuransi')
    product_category_id = fields.Many2one('product.category', domain= [('name', 'in', ['Transporter', 'VLI', 'Trucking'])], required=True)
    branch_project = fields.Selection(
        selection=BRANCH_PROJECT,
        readonly=1,
        default=lambda self: str(self.env.company.company_code).lower()
    if str(self.env.company.company_code).lower() in [code for code, label in BRANCH_PROJECT]
    else False
    )
    delivery_category_id = fields.Many2one('delivery.category','Delivery Category')
    po_ids = fields.One2many('sale.order', 'contract_id')
    po_count = fields.Integer(compute='compute_po_count')
    payment_term_id = fields.Many2one('account.payment.term', string="Customer Payment Term", related='partner_id.property_payment_term_id', store=True, readonly=False)
    invoice_policy = fields.Selection(
        [("order", "CBD"), ("delivery", "TOP")],
        help="CBD: Cash Before Delivery.\n"
             "TOP: Term Of Payment. ",
    )
    integrated = fields.Selection([
        ('half', 'Half Integrated'),
        ('full', 'Fully Integrated'),
        ('one_trip', 'One Trip'),
        ('round_trip', 'Round Trip'),
    ], string="Integration")
    delivery_name = fields.Char(related='delivery_category_id.name')
    product_name = fields.Char(related='product_category_id.name')
    cust_contract_name = fields.Char(string='Nomor Contract Customer')
    invoiced_by = fields.Selection([('volume', 'Volume'),('tonase', 'Tonase'), ('ritase', 'Ritase')], 'Invoiced By', required=True)
    
    company_portfolio = fields.Char(
        string="Company Portfolio",
        compute="_compute_company_portfolio",
        store=False,
        default=lambda self: self.env.company.portfolio_id.name
    )

    def _compute_company_portfolio(self):
        for rec in self:
            rec.company_portfolio = rec.env.company.portfolio_id.name or False

    @api.model
    def _generate_contract_name(self, code):
        sequence_code = 'create.contract' + '.' + code
        nomor_urut = self.env['ir.sequence'].next_by_code(sequence_code) or '00000'
        bulan = datetime.today().month
        tahun = datetime.today().year
        kode = code if code else 'LMKS'
        return f'{nomor_urut}/{kode}/{bulan}/{tahun}'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False):
        args = list(args or [])  # pastikan args bisa ditambahkan
        user_company_ids = self.env.user.company_ids.ids

        if user_company_ids:
            args.append(('company_ids', 'in', user_company_ids))

        return super(CreateContract, self)._search(args, offset=offset, limit=limit, order=order)


    def write(self, vals):
        updated_bop_lines = []
        for order in self:
            start = vals.get('start_date') or order.start_date
            end = vals.get('end_date') or order.end_date

            if isinstance(start, str):
                start = fields.Date.from_string(start)
            if isinstance(end, str):
                end = fields.Date.from_string(end)

            if start and end and start > end:
                raise ValidationError("Start Date tidak boleh lebih besar dari End Date.")

            if 'line_ids' in vals:
                for idx, val in enumerate(vals.get('line_ids')):
                    if len(val) < 3:
                        continue
                    if 'new_price' in vals['line_ids'][idx][2]:
                        message = f"New Price changed to {vals['line_ids'][idx][2]['new_price']}."
                        order.message_post(body=message)
                    if 'updated' in vals['line_ids'][idx][2]:
                        message = f"Updated on {vals['line_ids'][idx][2]['updated']}."
                        order.message_post(body=message)
                    if 'bop' in vals['line_ids'][idx][2]:
                        updated_bop_lines.append(vals['line_ids'][idx])

        # Proceed with the original write method
        res = super(CreateContract, self).write(vals)

        print('len(updated_bop_lines)', len(updated_bop_lines), updated_bop_lines)
        if len(updated_bop_lines) > 0:
            # format result updated_bop_lines => [[1, 186, {'bop': 9000}]]
            for line in updated_bop_lines:
                line_id = line[1]
                line_bop = line[2]['bop'] if 'bop' in line[2] else 0
                if isinstance(line_id, int):
                    query_update_bop = """
                        UPDATE create_contract_line
                        SET bop = %s
                        WHERE id = %s
                    """
                    self.env.cr.execute(query_update_bop, (line_bop, line_id))
                    self.env.cr.commit()

        return res

    def compute_po_count(self):
        for rec in self:
            rec.po_count = len(rec.po_ids)

    def action_view_po(self):
        action = self.env.ref('jst_demo_kalla_bju_transporter.sale_order_transporter_action').read()[0]
        # form_view_id = self.env.ref('jst_demo_kalla_bju_transporter.transporter_sale_order_form').id
        action.update({
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.po_ids.ids)],
        })
        return action

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.customer_product_ids = [(6, 0, self.partner_id.customer_product_ids.ids)]
        else:
            self.customer_product_ids = [(5, 0, 0)]  # Clear all records

    @api.depends('partner_id')
    def _compute_partner_details(self):
        for record in self:
            if record.partner_id:
                record.phone = record.partner_id.phone
                record.email = record.partner_id.email
            else:
                record.phone = False
                record.email = False

    def action_contract_quotations_new(self):
        sale_order = self.env['sale.order']
        order_line = []
        product_detail = []
        for rec in self:
            selected_lines = rec.line_ids.filtered(lambda l: l.is_line)
            qty_ritase_total = sum(selected_lines.mapped('qty_ritase'))

            if not selected_lines:
                raise UserError("Mohon ceklist line yang ingin dijadikan SO terlebih dahulu.")

            if len(selected_lines) > 1:
                raise UserError(
                    "Pembuatan Sales Order tidak dapat dilanjutkan karena terdapat lebih dari satu contract line yang dipilih. Mohon buat Sales Order terpisah untuk setiap contract line.")

            # for line in selected_lines:
            #     if line.bop == 0:
            #         raise UserError(
            #             "Biaya BOP tidak ditemukan. Silakan lengkapi terlebih dahulu di modul Fleet, menu Formula BOP.")

            for line in rec.line_ids:
                if not line.is_line:
                    continue

                analytic_distribution = None
                if rec.product_category_id and rec.product_category_id.id:
                    analytic_account = self.env['sale.order']._get_or_create_analytic_account(rec.product_category_id.name)
                    if analytic_account:
                        analytic_distribution = {str(analytic_account.id): 100}

                is_tam = rec.partner_id.is_tam
                is_vli_or_customer_tam = (rec.product_name == 'VLI' or is_tam)

                order_line.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'price_unit': line.price,
                    'origin_id': line.origin_id.id,
                    'destination_id': line.destination_id.id,
                    'is_line': line.is_line,
                    'is_handling_type': line.is_handling_type,
                    'id_contract': line.id_contract,
                    'distance': line.distance,
                    'sla': line.sla,
                    'qty_tonase': line.qty_tonase,
                    'qty_kubikasi': line.qty_kubikasi,
                    'qty_unit': line.qty_unit if not is_vli_or_customer_tam else 0,
                    'qty_dus': line.qty_dus,
                    'qty_ritase': line.qty_ritase,
                    'qty_target_ritase': line.qty_target_ritase,
                    'contract_qty_ritase': qty_ritase_total if not is_tam else 0,
                    'bop': line.bop,
                    'can_update_analytic_distribution_via_so': False,
                    'analytic_distribution': analytic_distribution,
                    'tax_id': line.product_id.partner_tax_ids.filtered(lambda x: x.partner_id.id == rec.partner_id.id).tax_ids if line.product_id.partner_tax_ids.filtered(lambda x: x.partner_id.id == rec.partner_id.id) else None
                }))

            checked_products = rec.product_detail_ids.filtered(lambda pd: pd.go_to_so)
            if len(checked_products) < 1 and is_vli_or_customer_tam:
                raise ValidationError(_(f"Belum ada baris yang di centang pada tab \"Detail Order\""))
            # details = checked_products if is_vli_or_customer_tam else []
            # if len(details) > 0: 
            for line in checked_products:
                product_detail.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_code': line.product_code,
                    'ce_code': rec.line_ids.filtered(lambda pd: pd.is_line).id_contract,
                    'name': line.product_description if line.product_description else line.product_id.name,
                    'price_unit': line.unit_price,
                    'quantity': line.qty,
                    'qty_tonase': line.qty_tonase,
                    'qty_ritase': line.qty_ritase,
                    'qty_kubikasi': line.qty_kubikasi,
                    'uom_id': line.uom_id.id if line.uom_id else line.product_id.uom_id.id,
                    'route_category_id': line.route_category_id.id,
                    'origin_id': line.origin_id.id,
                    'destination_id': line.destination_id.id,
                }))

            so_bp_value = dict(self._fields['branch_project'].selection).get(self.branch_project)
            so_name = self.env['sale.order']._generate_fleet_so_name(so_bp_value)
            new_so = sale_order.create({
                'name': so_name,
                'opportunity_id': rec.crm_id.id,
                'is_created_from_contract': True,
                'partner_id': rec.partner_id.id,
                'company_id': rec.company_id.id,
                'origin': rec.name,
                'user_id': rec.responsible_id.id,
                'team_id': rec.crm_id.team_id.id,
                'contract_id': rec.id,
                'branch_project': rec.branch_project,
                'product_category_id': rec.product_category_id.id,
                'delivery_category_id': rec.delivery_category_id.id,
                'order_line': order_line,
                'sale_order_option_ids': product_detail,
                'invoice_policy': rec.invoice_policy,
                'integrated': rec.integrated if rec.delivery_category_id.name == 'Door to Door' else 'half',
                'invoiced_by': rec.invoiced_by,
            })

            # Hanya untuk memastikan Invoice Policy ter-generate
            new_so.sudo().write({
                'invoice_policy': rec.invoice_policy,
            })
            action = self.env.ref('jst_demo_kalla_bju_transporter.sale_order_transporter_action').read()[0]
            form_view_id = self.env.ref('jst_demo_kalla_bju_transporter.transporter_sale_order_form').id
            for line in self.line_ids.filtered(lambda isline: isline.is_line):
                line.is_line = False
            action.update({
                'res_id': new_so.id,
                'view_mode': 'form',
                'target': 'current',
                'views': [(form_view_id, 'form')],
            })
            return action

    def unlink(self):
        for rec in self:
            if rec.po_ids:
                raise UserError('Tidak bisa dihapus karena sudah memiliki minimal 1 Sales Order terkait.')
        return super(CreateContract, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        to_date = fields.Date.to_date
        # validasi per baris sebelum create
        for vals in vals_list:
            start = vals.get('start_date')
            end = vals.get('end_date')

            if isinstance(start, str):
                start = to_date(start)
            if isinstance(end, str):
                end = to_date(end)
            if start and end and start > end:
                raise ValidationError("Start Date tidak boleh lebih besar dari End Date.")

        recs = super().create(vals_list)

        sel = dict(self._fields['branch_project'].selection)
        for rec in recs:
            bp_name = sel.get(rec.branch_project)
            if bp_name:
                rec.name = self._generate_contract_name(bp_name)

        return recs


class CreateContractLine(models.Model):
    _name = 'create.contract.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'id_contract'

    contract_id = fields.Many2one('create.contract')
    # name = fields.Char()
    # vehicle_id = fields.Many2one(comodel_name='product.template')
    # vehicle_category_id = fields.Many2one('fleet.vehicle.model.category')
    product_id = fields.Many2one('product.product', 'CATEGORY UNIT')
    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
    distance = fields.Integer('DISTANCE (KM)')
    sla = fields.Integer('SLA DELIVERY (Day)')
    qty_tonase = fields.Float('TONASE (Ton)')
    qty_kubikasi = fields.Float('VOLUME (Kubikasi)')
    qty_unit = fields.Float('UNIT/PCS')
    qty_dus = fields.Float('DUS/BOX')
    qty_ritase = fields.Float('RITASE')
    qty_target_tonase = fields.Float('TARGET TONASE')
    qty_target_ritase = fields.Float('TARGET RITASE (Trucking)')
    qty_actual_tonase = fields.Float('ACTUAL TONASE')
    currency_id = fields.Many2one('res.currency', related='contract_id.company_id.currency_id')
    price = fields.Monetary('PRICE', currency_field='currency_id')
    bop = fields.Monetary('BOP', currency_field='currency_id', compute="compute_bop", readonly=True, store=True)
    id_contract = fields.Char('CE. CODE')
    is_handling_type = fields.Boolean('HANDLING')
    is_line = fields.Boolean('LINE')
    start_date_event = fields.Date('Start Date Event')
    end_date_event = fields.Date('End Date Event')
    active = fields.Boolean('Status', default=True)
    start_date = fields.Date('Start Date', tracking=True)
    end_date = fields.Date('End Date', tracking=True)
    product_domain = fields.Json(
        compute='_compute_product_domain',
        store=False,  # keep it transient; recompute on form changes
    )

    # Add a flag to prevent BOP recalculation when explicitly set
    _skip_bop_compute = fields.Boolean(default=False, store=False)

    @api.depends(
        'contract_id.integrated',
        'contract_id.delivery_category_id',
        'contract_id.delivery_category_id.name',
    )
    def _compute_product_domain(self):
        # Cache category IDs untuk menghindari query berulang
        ProductCategory = self.env['product.category']
        category_map = {
            'all': ProductCategory.search([('name', 'in', ['Transporter', 'VLI', 'Trucking'])]).ids,
            'transporter_trucking': ProductCategory.search([('name', 'in', ['Transporter', 'Trucking'])]).ids,
            'vli': ProductCategory.search([('name', '=', 'VLI')]).ids
        }

        for rec in self:
            contract = rec.contract_id
            product_category_name = contract.product_category_id.name.upper() if contract.product_category_id else ''
            delivery_category_name = getattr(contract.delivery_category_id, 'name', None)

            # Determine domain berdasarkan kondisi
            if delivery_category_name == 'Self Drive':
                domain = [('name', 'ilike', 'Self Drive')]
            elif product_category_name == 'VLI':
                domain = [('categ_id', 'in', category_map['vli'])]
            elif product_category_name in ['TRANSPORTER', 'TRUCKING']:
                domain = [('categ_id', 'in', category_map['transporter_trucking'])]
            else:
                domain = [('categ_id', 'in', category_map['all'])]

            # Tambahkan filter khusus untuk half integration + Door to Door
            if (contract.integrated == 'half' and
                    delivery_category_name == 'Door to Door'):
                domain.append(('vehicle_category_id.is_shipment', '=', False))

            rec.product_domain = domain

    # product_variant_id = fields.Many2one('detail.product.variant', string='Product Variant')

    @api.model_create_multi
    def create(self, vals_list):
        # Validasi dulu sebelum create
        for vals in vals_list:
            start = vals.get('start_date')
            end = vals.get('end_date')
            qty_tonase = vals.get('qty_tonase')
            qty_unit = vals.get('qty_unit')
            volume = vals.get('qty_kubikasi')

            contract_id = vals.get('contract_id')
            contract = self.env['create.contract'].browse(contract_id) if contract_id else None
            category = contract.product_category_id
            category_name = category.name if category else ""

            if isinstance(start, str):
                start = fields.Date.from_string(start)
            if isinstance(end, str):
                end = fields.Date.from_string(end)

            if start and end and start > end:
                raise ValidationError(_("Start Date tidak boleh lebih besar dari End Date."))

            product_id = vals.get('product_id')
            product = self.env['product.product'].browse(product_id)

            if category_name in ['Transporter', 'Trucking']:
                # if not qty_tonase or (qty_tonase and qty_tonase < 1):
                #     raise ValidationError(_("Qty Tonase harus diisi jika kategori 'Transporter' atau 'Trucking'"))

                if product and product.vehicle_category_id:
                    min_tonase = product.vehicle_category_id.min_tonase or 0.0
                    max_tonase = product.vehicle_category_id.max_tonase or 0.0
                    min_volume = product.vehicle_category_id.min_kubikasi or 0.0
                    max_volume = product.vehicle_category_id.max_kubikasi or 0.0

                    if (qty_tonase and qty_tonase < min_tonase) or (qty_tonase and qty_tonase > max_tonase):
                        raise ValidationError('Qty Tonase Tidak Sesuai dengan kategori di line')
                    if (volume and volume < min_volume) or (volume and volume > max_volume):
                        raise ValidationError('Qty Volume / Kubikasi Tidak Sesuai dengan kategori di line')
                else:
                    raise ValidationError('Produk belum memiliki kategori kendaraan yang sesuai')

            elif category_name == 'VLI':
                # if not qty_unit or (qty_unit and qty_unit < 1):
                #     raise ValidationError(_("Qty Unit harus diisi jika kategori 'VLI'"))

                if product and product.vehicle_category_id:
                    max_unit = product.vehicle_category_id.max_unit or 0.0
                    if qty_unit > max_unit:
                        raise ValidationError('Qty Unit Tidak Sesuai dengan Category di line')
                else:
                    raise ValidationError('Produk belum memiliki kategori kendaraan yang sesuai')


            sequence = self.env['ir.sequence'].next_by_code('create.contract.line')
            partner_code = self.contract_id.browse(vals['contract_id']).partner_id.customer_code
            vals['id_contract'] = partner_code + sequence if partner_code else '' + sequence

        return super().create(vals_list)

    @api.model
    def write(self, vals):
        # Check if BOP is being explicitly updated via direct database operation
        # If so, skip compute_bop to avoid overwriting the manual value
        if 'bop' in vals:
            self._skip_bop_compute = True

        start = vals.get('start_date')
        end = vals.get('end_date')
        qty_tonase = vals.get('qty_tonase', self.qty_tonase)
        qty_unit = vals.get('qty_unit', self.qty_unit)
        volume = vals.get('qty_kubikasi', self.qty_kubikasi)

        category = self.contract_id.product_category_id
        category_name = category.name if category else ""

        if isinstance(start, str):
            start = fields.Date.from_string(start)
        if isinstance(end, str):
            end = fields.Date.from_string(end)

        if start and end and start > end:
            raise ValidationError("Start Date tidak boleh lebih besar dari End Date.")

        product = self.product_id

        if category_name in ['Transporter', 'Trucking']:
            # if not qty_tonase or (qty_tonase and qty_tonase < 1):
            #     raise ValidationError(_("Qty Tonase harus diisi jika kategori 'Transporter' atau 'Trucking'"))

            if product and product.vehicle_category_id:
                min_tonase = product.vehicle_category_id.min_tonase or 0.0
                max_tonase = product.vehicle_category_id.max_tonase or 0.0
                min_volume = product.vehicle_category_id.min_kubikasi or 0.0
                max_volume = product.vehicle_category_id.max_kubikasi or 0.0

                if (qty_tonase and qty_tonase < min_tonase) or (qty_tonase and qty_tonase > max_tonase):
                    raise ValidationError('Qty Tonase Tidak Sesuai dengan kategori di line')
                if (volume and volume < min_volume) or (volume and volume > max_volume):
                    raise ValidationError('Qty Volume / Kubikasi Tidak Sesuai dengan kategori di line')
            else:
                raise ValidationError('Produk belum memiliki kategori kendaraan yang sesuai')

        elif category_name == 'VLI':
            # if not qty_unit or (qty_unit and qty_unit < 1):
            #     raise ValidationError(_("Qty Unit harus diisi jika kategori 'VLI'"))

            if product and product.vehicle_category_id:
                max_unit = product.vehicle_category_id.max_unit or 0.0
                if qty_unit > max_unit:
                    raise ValidationError('Qty Unit Tidak Sesuai dengan Category di line')
            else:
                raise ValidationError('Produk belum memiliki kategori kendaraan yang sesuai')

        # Jika ada record yang diubah menjadi inactive, simpan ke archive
        if 'active' in vals and vals['active'] is False:
            for line in self:
                self.env['create.contract.line.archive'].create({
                    'original_line_id': line.id,
                    'contract_id': line.contract_id.id,
                    'product_id': line.product_id.id,
                    'origin_id': line.origin_id.id,
                    'destination_id': line.destination_id.id,
                    'distance': line.distance,
                    'sla': line.sla,
                    'qty_tonase': line.qty_tonase,
                    'qty_kubikasi': line.qty_kubikasi,
                    'qty_unit': line.qty_unit,
                    'qty_dus': line.qty_dus,
                    'qty_ritase': line.qty_ritase,
                    'price': line.price,
                    'bop': line.bop,
                    'currency_id': line.currency_id.id,
                    'id_contract': line.id_contract,
                    'start_date': line.start_date,
                    'end_date': line.end_date,
                })

        return super(CreateContractLine, self).write(vals)

    # cutomer = partner_id , category_id = product_id
    @api.depends('contract_id.partner_id', 'origin_id', 'destination_id', 'product_id')
    def compute_bop(self):
        for line in self:
            # Skip computation if BOP is being explicitly set
            if hasattr(line, '_skip_bop_compute') and line._skip_bop_compute:
                continue

            line.bop = 0.0  # Initialize with default value

            # Only proceed if all required fields have values
            if not (line.contract_id and line.contract_id.partner_id and
                    line.product_id and line.product_id.vehicle_category_id and
                    line.destination_id and line.origin_id):
                continue

            try:
                formula_bop = self.env['fleet.bop'].search(
                    [
                        ("customer", "=", line.contract_id.partner_id.id),
                        ("origin_id", "=", line.origin_id.id),
                        ("destination_id", "=", line.destination_id.id),
                        ("category_id", "=", line.product_id.vehicle_category_id.id),
                    ],
                    limit=1,
                )
                if formula_bop:
                    line.bop = formula_bop.total_bop
                # else:
                #     raise Exception(_('No BOP Found'))
            except Exception as e:
                # Log the error but don't crash
                if str(e) == 'No BOP Found':
                    raise UserError(_(str(e)))
                _logger.error(f"Error computing BOP for line {line.id}: {str(e)}")

    @api.onchange('product_id', 'origin_id', 'destination_id')
    def _onchange_bop_lookup(self):
        for line in self:
            # Reset values before searching
            line.distance = 0
            line.sla = 0

            if not (line.contract_id and line.contract_id.partner_id and
                    line.product_id and line.product_id.vehicle_category_id and
                    line.origin_id and line.destination_id):
                continue

            formula_bop = self.env['fleet.bop'].search([
                ('customer', '=', line.contract_id.partner_id.id),
                ('origin_id', '=', line.origin_id.id),
                ('destination_id', '=', line.destination_id.id),
                ('category_id', '=', line.product_id.vehicle_category_id.id),
            ], limit=1)

            if formula_bop:
                line.distance = formula_bop.total_distance
                line.sla = formula_bop.total_cycle_time_day
            # else:
            #     raise UserError("No matching BOP formula found. Please check the data in Fleet > Formula BOP.")

class CreateContractLineArchive(models.Model):
    _name = 'create.contract.line.archive'
    _description = 'Archived Contract Lines (Inactive)'

    original_line_id = fields.Many2one('create.contract.line', string='Original Line', readonly=True)
    contract_id = fields.Many2one('create.contract', string='Contract', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    origin_id = fields.Many2one('master.origin', string='Origin', readonly=True)
    destination_id = fields.Many2one('master.destination', string='Destination', readonly=True)
    distance = fields.Integer('Distance (KM)', readonly=True)
    sla = fields.Integer('SLA Delivery (Day)', readonly=True)
    qty_tonase = fields.Float('Tonase', readonly=True)
    qty_kubikasi = fields.Float('Volume (Kubikasi)', readonly=True)
    qty_unit = fields.Float('Unit/PCS', readonly=True)
    qty_dus = fields.Float('Dus/Box', readonly=True)
    qty_ritase = fields.Float('Ritase', readonly=True)
    price = fields.Monetary('Price', readonly=True)
    bop = fields.Monetary('BOP', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    id_contract = fields.Char('CE. Code', readonly=True)
    start_date = fields.Date('Start Date', readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    archived_date = fields.Datetime('Archived On', default=fields.Datetime.now)
    product_domain = fields.Json(
        compute='_compute_product_domain',
        store=False,  # keep it transient; recompute on form changes
    )
    is_active = fields.Boolean(readonly=False)

    @api.depends(
        'contract_id.integrated',
        'contract_id.delivery_category_id',
        'contract_id.delivery_category_id.name',
    )
    def _compute_product_domain(self):
        # Cache category IDs untuk menghindari query berulang
        ProductCategory = self.env['product.category']
        category_map = {
            'all': ProductCategory.search([('name', 'in', ['Transporter', 'VLI', 'Trucking'])]).ids,
            'transporter_trucking': ProductCategory.search([('name', 'in', ['Transporter', 'Trucking'])]).ids,
            'vli': ProductCategory.search([('name', '=', 'VLI')]).ids
        }

        for rec in self:
            contract = rec.contract_id
            product_category_name = contract.product_category_id.name.upper() if contract.product_category_id else ''
            delivery_category_name = getattr(contract.delivery_category_id, 'name', None)

            # Determine domain berdasarkan kondisi
            if delivery_category_name == 'Self Drive':
                domain = [('name', 'ilike', 'Self Drive')]
            elif product_category_name == 'VLI':
                domain = [('categ_id', 'in', category_map['vli'])]
            elif product_category_name in ['TRANSPORTER', 'TRUCKING']:
                domain = [('categ_id', 'in', category_map['transporter_trucking'])]
            else:
                domain = [('categ_id', 'in', category_map['all'])]

            # Tambahkan filter khusus untuk half integration + Door to Door
            if (contract.integrated == 'half' and
                    delivery_category_name == 'Door to Door'):
                domain.append(('vehicle_category_id.is_shipment', '=', False))

            rec.product_domain = domain


class DetailProductVariant(models.Model):
    _name = 'detail.product.variant'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    contract_id = fields.Many2one('create.contract')
    product_code = fields.Char('PRODUCT CODE')
    # ce_code = fields.Char('CE. CODE')
    product_id = fields.Many2one('product.product', 'PRODUCT NAME')
    product_description = fields.Text('DESCRIPTION')
    qty = fields.Integer('QUANTITY')
    uom_id = fields.Many2one('uom.uom', 'UoM')
    qty_tonase = fields.Float('TONASE (Ton)')
    qty_kubikasi = fields.Float('VOLUME (Kubikasi)')
    qty_ritase = fields.Float('RITASE')
    currency_id = fields.Many2one('res.currency', related='contract_id.company_id.currency_id')
    unit_price = fields.Monetary('UNIT PRICE', currency_field='currency_id')
    ce_code = fields.Many2one(
        'create.contract.line',
        string='CE. CODE',
        domain="[('contract_id', '=', contract_id)]",
    )
    go_to_so = fields.Boolean('Go To SO')
    route_category_id = fields.Many2one('product.attribute', 'Route Category')
    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
    product_domain = fields.Char(compute="_compute_product_domain")

    @api.depends('route_category_id')
    def _compute_product_domain(self):
        for rec in self:
            if rec.route_category_id:
                list_product = rec.product_id.search([('attribute_line_ids.attribute_id', '=', rec.route_category_id.id)]).ids
                rec.product_domain = json.dumps(
                    [('id', 'in', list_product)]
                )
            else:
                rec.product_domain = json.dumps(
                    [(1, '=', 1)]
                )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                origin = rec.product_id.product_template_attribute_value_ids.product_attribute_value_id.origin_id
                destination = rec.product_id.product_template_attribute_value_ids.product_attribute_value_id.destination_id
                rec.origin_id = origin if origin else False
                rec.destination_id = destination if destination else False

    @api.model
    # def _get_ce_code_selection(self):
    #     # contract_id = self.env.context.get('contract_id')
    #     # contract_id = self.contract_id.id
    #     contract_id = self.env.context.get('contract_id')
    #     print("contract_id from context:", contract_id)
    #     # print(contract_id)
    #     contract_lines = self.env['create.contract.line'].search([
    #         ('contract_id', '=', contract_id)
    #     ])
    #     values = set()
    #     for line in contract_lines:
    #         if line.id_contract:
    #             values.add((line.id_contract, line.id_contract))
    #     return sorted(values)

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            contract_lines = self.env['create.contract.line'].search([
                ('contract_id', '=', self.contract_id.id)
            ])
            if contract_lines:
                self.ce_code = contract_lines[0].id_contract  # Ambil yang pertama saja