# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import requests
import logging
import math
from odoo.tools import float_round

from odoo.tools.populate import compute
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round, float_compare, float_is_zero


_logger = logging.getLogger(__name__)

_REVIEW_TARGET_BY_STATE = {
    'to_approve':             'approved_operation_spv',
    'approved_operation_spv': 'approved_cashier',
    'approved_cashier':       'approved_adh',
    'approved_adh':           'approved_by_kacab',
    'approved_by_kacab':      'approved_by_kacab',
}

_REVIEW_TARGET_BY_STATE_BOP = {
    'draft': 'approved_cashier',
    'approved_cashier':       'approved_adh',
    'approved_adh':           'approved_by_kacab',
    'approved_by_kacab':      'approved_by_kacab',
}

class FleetDo(models.Model):
    _name = 'fleet.do'
    _inherit = ['tier.validation','mail.thread', 'mail.activity.mixin', 'portfolio.view.mixin']
    _description = 'Delivery Order Fleet'
    _rec_name = 'name'
    _order = 'create_date desc'

    _tier_validation_manual_config = True

    do_id = fields.Char(tracking=True)
    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False
    )
    geofence_loading_id = fields.Many2one('fleet.geofence', domain=[('geo_type_nm', 'ilike', 'asal')])
    geofence_unloading_id = fields.Many2one('fleet.geofence', domain=[('geo_type_nm', 'ilike', 'tujuan')])
    sale_id = fields.Many2one('sale.order')
    driver_id = fields.Many2one('res.partner', tracking=True)
    sale_line_id = fields.Many2one('sale.order.line')
    vehicle_id = fields.Many2one('fleet.vehicle', tracking=True)
    category_id = fields.Many2one('fleet.vehicle.model.category', tracking=True)
    date = fields.Date(tracking=True)
    plan_loading_time = fields.Datetime(string="Plan Loading Time", tracking=True)
    plan_unloading_time = fields.Datetime(string="Plan Unloading Time", tracking=True)
    partner_id = fields.Many2one('res.partner', tracking=True)
    tag_ids = fields.Many2many('res.partner.category', string='Tags', compute='compute_tag_ids', store=True)
    note = fields.Text(tracking=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('to_approve', 'To Approve'),
                              ('approved_operation_spv', 'Approved Operation Supervisor'),
                              ('approved_cashier', 'Approved Cashier'),
                              ('approved_adh', 'Approved Administration Head'),
                              ('approved_by_kacab', 'Approved Kepala Cabang'),
                              ('done', 'Done'),
                              ('cancel', 'Cancel')], default='draft', tracking=True)
    status_do = fields.Char(compute='compute_status_do', store=True)
    origin_id = fields.Many2one('master.origin', 'Origin', compute='compute_origin', store=True)
    destination_id = fields.Many2one('master.destination', 'Destination', compute='compute_destination', store=True)
    access_approval = fields.Boolean(compute='compute_access_approval')
    line_ids = fields.One2many(comodel_name='fleet.do.line', inverse_name='fleet_do_id')
    reject_date = fields.Date('Reject Date')
    reject_by = fields.Many2one('res.users', 'Reject By')
    reject_note = fields.Text('Reject Note')
    approval_date_operation_spv = fields.Date('Approval Date')
    approval_by_operation_spv = fields.Many2one('res.users', 'Approval By')
    approval_note_operation_spv = fields.Text('Approval Note')
    approval_date_cashier = fields.Date('Approval Date')
    approval_by_cashier = fields.Many2one('res.users', 'Approval By')
    approval_note_cashier = fields.Text('Approval Note')
    approval_date_adh = fields.Date('Approval Date')
    approval_by_adh = fields.Many2one('res.users', 'Approval By')
    approval_note_adh = fields.Text('Approval Note')
    approval_date_by_kacab = fields.Date('Approval Date')
    approval_by_kacab  = fields.Many2one('res.users', 'Approval By')
    approval_note_by_kacab = fields.Text('Approval Note')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)
    nominal = fields.Monetary(currency_field='currency_id', compute='compute_nominal')
    prev_nominal = fields.Monetary(currency_field='currency_id', string='Summary', compute='compute_prev_nominal')
    bop_no = fields.Char('BOP No')
    bop_paid = fields.Monetary('BOP Paid', currency_field='currency_id', store=True)
    bop_percentage_paid = fields.Float('BOP Percentage Paid', compute='compute_bop')
    bop_unpaid = fields.Monetary('BOP Unpaid', currency_field='currency_id', compute='compute_bop')
    no_lambung = fields.Char('No Lambung',compute='compute_no_lambung')
    source_bop = fields.Char()
    note_bop = fields.Text()
    transfer_to = fields.Many2one('res.partner', compute='compute_transfer_to', store=True)
    manifest_no = fields.Char('Manifest No')
    bank_cash = fields.Many2one('account.journal', 'Bank / Cash', related='transfer_to.bank_cash', store=True)
    rekening_number = fields.Char('No. Rekening', compute='compute_transfer_to', store=True)
    rekening_name = fields.Char('Nama Rekening', compute='compute_transfer_to', store=True)
    rekening_bank = fields.Char('Nama Bank', store=True, readonly=True)
    bank_name = fields.Many2one('res.partner.bank')
    journal_entry_ids = fields.One2many('account.move', inverse_name='fleet_id')
    # hpp = fields.Float(currency_field='currency_id', related='vehicle_id.x_studio_total_hpp', store=True)
    # revenue = fields.Float(currency_field='currency_id', related='vehicle_id.x_studio_total_revenue', store=True)
    margin = fields.Float(currency_field='currency_id', compute='compute_margin', store=True)
    margin_percentage = fields.Float(currency_field='currency_id', compute='compute_margin', store=True)
    bop_state = fields.Selection([
        ('partial', 'Partial Payment'),
        ('full', 'Full Payment'),
    ], compute='_compute_bop_state', store=True, tracking=True)
    po_line_ids = fields.Many2many(
        'sale.order.line', relation='do_po_line_rel', column1='do_id', column2='po_line_id', tracking=True
    )
    reference = fields.Char('DO References')
    product_category_id = fields.Many2one('product.category', 'Product Category')
    delivery_category_id = fields.Many2one('delivery.category', 'Delivery Category')
    delivery_category_name = fields.Char('Delivery Category', related="delivery_category_id.name")
    do_product_variant_ids = fields.One2many(comodel_name='fleet.do.option', inverse_name='fleet_do_id')
    status_document = fields.Selection([('good_receive', 'Good Receive'),
                                       ('incompleted', 'Document Incompleted')], string='Status Delivery Document', store=True)
    # status_document_status = fields.Char(string='Status Delivery Document', compute='compute_status_document', store=True)
    status_document_status = fields.Char(string='Status Delivery Document', store=True, readonly=True)
    is_match_do = fields.Boolean('Kesesuaian Surat jalan dengan DO line', store=True)
    is_match_po = fields.Boolean('Kesesuaian Nilai PO di surat jalan dengan yang di DO', store=True)
    attach_doc_complete = fields.Boolean('Document Fisik Lengkap', store=True)
    bop_ids = fields.One2many(comodel_name='bop.line', inverse_name='fleet_do_id')
    # route_id = fields.Many2one('fleet.route', string='Route', default=False, tracking=True)
    no_bbm = fields.Char('No Tiket BBM', tracking=True)
    jam_isi = fields.Float('Jam Isi')
    fuel_in  = fields.Float('Fuel IN')
    vendor_bbm_id = fields.Many2one('res.partner', string="Vendor BBM")
    odometer = fields.Float('Odometer')
    fuel_in_status = fields.Char('Fuel IN Status')
    # bop_percentage = fields.Float(digits=(16, 2), compute='compute_bop_percentage', store=True)
    # bop_percentage_display = fields.Char(string="BOP / Revenue (persentasi)", compute="compute_bop_percentage_display")
    contract_line_id = fields.Many2one('create.contract.line', string='Contract Line')
    sla_delivery = fields.Integer(string='SLA DELIVERY (Day)', compute='compute_sla_delivery', store=True)
    invoice_id = fields.Many2one('account.move', string='Vendor Bill')
    amount_total = fields.Monetary(string='Total', currency_field='currency_id')
    tonase_line = fields.Float(compute='_compute_volume', store=True)
    kubikasi_line = fields.Float(compute='_compute_volume', store=True)
    is_success_send_to_tms = fields.Boolean(store=True, default=False)
    # sale_line_id = fields.Many2one('sale.order.line', string="SO Line")
    review_ids = fields.One2many(
        comodel_name="tier.review",
        inverse_name="res_id",
        compute='_compute_review_ids_filtered',
        string="Riwayat Persetujuan DO",
    )
    bop_readonly = fields.Integer(compute='_compute_bop_readonly', store="True")
    status_locked = fields.Boolean(default=False, store=True)
    # route_id = fields.Selection(selection='_get_route_selection', string='Route', tracking=True)
    # route_id = fields.Many2one('m.fleet.route', string='Route', default=False, tracking=True)
    route_id = fields.Many2one('fleet.route', string='Route', default=False, tracking=True)
    route_ids = fields.Many2one('m.fleet.route', string='Route', tracking=True)
    has_access_state = fields.Boolean(default=False, compute='_compute_has_access_state')
    filtered_bop_ids = fields.One2many(
        'bop.line',
        compute='_compute_filtered_bop_ids',
        string='Filtered BOP IDs',
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        ondelete='set null',
        tracking=True
    )
    has_purchase_order = fields.Boolean(
        compute='_compute_has_purchase_order',
        string='Has Purchase Order'
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_order_count',
        string='Purchase Order Count'
    )
    current_reviewer_id = fields.Many2one('res.users', string='Current Reviewer', index=True)
    integrated = fields.Selection([
        ('half', 'Half Integrated'),
        ('full', 'Fully Integrated'),
        ('one_trip', 'One Trip'),
        ('round_trip', 'Round Trip'),
    ], string="Integration")
    delivery_name = fields.Char(related='delivery_category_id.name')
    asset_type_name = fields.Selection([
        ('asset', 'Asset'),
        ('vendor', 'Vendor')
    ], related='vehicle_id.asset_type')
    is_already_do_match = fields.Boolean(compute="_compute_is_already_do_match", store=True)
    is_already_do_unmatch = fields.Boolean(compute="_compute_is_already_do_unmatch", store=True)
    asset_type = fields.Selection(
        related='vehicle_id.asset_type',
        store=True, readonly=True
    )
    fleet_owner = fields.Many2one(
        'res.partner',
        string='Fleet Owner',
        domain=[('is_company', '=', True)],
        required=True,
        related="vehicle_id.vichle_ownership"
    )
    bop_driver_used = fields.Float('BOP Driver yang digunakan')
    remaining_bop_driver_has_been_converted_to_bill = fields.Boolean()
    is_vli_category = fields.Boolean(
        compute='_compute_is_vli_category',
        store=True
    )

    @api.depends('product_category_id', 'product_category_id.name')
    def _compute_is_vli_category(self):
        for record in self:
            record.is_vli_category = (
                str(record.product_category_id.name).upper() == 'VLI'
                if record.product_category_id else False
            )

    _sql_constraints = [
        ('unique_purchase_order', 'unique(purchase_order_id)',
         'Purchase Order hanya dapat dihubungkan dengan satu Fleet DO!')
    ]

    def _tier_def(self, review_state):
        TierDef = self.env['tier.definition']
        domain = [('review_state', '=', review_state)]
        if 'model_id' in TierDef._fields:
            domain.append(('model_id.model', '=', self._name))
        else:
            domain.append(('model', '=', self._name))
        return TierDef.search(domain, limit=1)

    def _close_my_todo_activity(self):
        todo = self.env.ref('mail.mail_activity_data_todo')
        acts = self.activity_ids.filtered(
            lambda a: a.activity_type_id.id == todo.id and a.user_id.id == self.env.user.id and not a.date_done
        )
        for act in acts:
            act.action_feedback(feedback=_("Approved by %s") % self.env.user.name)

    def _schedule_todo_for(self, user, summary, note):
        todo = self.env.ref('mail.mail_activity_data_todo')
        Activity = self.env['mail.activity'].sudo()
        exists = Activity.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', todo.id),
            ('user_id', '=', user.id),
            ('date_done', '=', False),
        ], limit=1)
        if not exists:
            # self.message_subscribe(partner_ids=[user.partner_id.id])
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=summary,
                note=note,
                date_deadline=fields.Date.today(),
            )

    def get_vehicle_selection_action(self):
        """
        Method untuk membuka popup selection vehicle dengan ordering dan callback
        """
        # Domain yang sama dengan yang ada di XML
        domain = [
            ('category_id', '=', self.category_id.id if self.category_id else False),
            ('vehicle_status', '=', 'ready'),
            ('driver_id.availability', '=', 'Ready'),
        ]

        # Tambahkan filter tonase dan kubikasi jika ada
        if self.tonase_line:
            domain.extend([
                ('category_id.min_tonase', '<=', self.tonase_line),
                ('category_id.max_tonase', '>=', self.tonase_line),
            ])

        if self.kubikasi_line:
            domain.extend([
                ('category_id.min_kubikasi', '<=', self.kubikasi_line),
                ('category_id.max_kubikasi', '>=', self.kubikasi_line),
            ])

        return {
            'name': 'Select Vehicle',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle',
            'view_mode': 'list',
            'view_type': 'form',
            'domain': domain,
            'context': {
                'search_default_order': 'date_of_status_ready asc',
                'default_order': 'date_of_status_ready asc',
                'fleet_do_id': self.id,  # Pass current record ID
                'select_vehicle_mode': False,  # Flag untuk mode selection
                'create': False,  # Disable create button
                'edit': False,  # Disable edit
            },
            'target': 'new',
            'flags': {
                'search_view': True,
                'action_buttons': False,  # Hide action buttons
            }
        }

    def set_selected_vehicle(self, vehicle_id):
        """
        Method untuk set vehicle yang dipilih dari popup
        """
        if vehicle_id:
            self.write({'vehicle_id': vehicle_id})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': 'Vehicle has been selected successfully.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        return False

    @api.depends('bop_ids.bop_no')
    def _compute_filtered_bop_ids(self):
        for rec in self:
            bop_lines = rec.bop_ids.filtered(lambda x: x.bop_no and x.bop_no.strip())
            rec.filtered_bop_ids = bop_lines

    @api.model
    def _generate_fleet_do_name(self, code):
        sequence_code = 'fleet.do'+'.'+code
        nomor_urut = self.env['ir.sequence'].next_by_code(sequence_code) or '00000'
        bulan = datetime.today().month
        tahun = datetime.today().year
        kode = code if code else 'LMKS'
        return f'DO/{nomor_urut}/{kode}/{bulan}/{tahun}'

    def _compute_has_access_state(self):
        for rec in self:

            state = ''
            if self.state == 'to_approve':
                state = 'approved_operation_spv'
            elif self.state == 'approved_operation_spv':
                state = 'approved_cashier'
            elif self.state == 'approved_cashier':
                state = 'approved_adh'
            elif self.state == 'approved_adh':
                state = 'approved_by_kacab'

            tier_definition = self.env['tier.definition'].search([
                ('review_state', '=', state),
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', self._name)
            ], limit=1)

            rec.has_access_state = bool(tier_definition)

    # @api.model
    # def _get_route_selection(self):
    #     routes = self.env['m.fleet.route'].search([])
    #     return [(route.geo_code, route.geo_code) for route in routes if route.geo_code]

    @api.depends('vehicle_id.model_id.category_id')
    def _compute_category_id(self):
        for record in self:
            record.category_id = record.vehicle_id.model_id.category_id

    @api.depends('state')
    def _compute_bop_readonly(self):
        for rec in self:
            rec.bop_readonly = 1 if rec.state not in ['approved_by_kacab', 'done'] else 0

    @api.constrains('bop_ids')
    def _check_bop_ids_modification(self):
        for rec in self:
            if rec.state in ['approved_by_kacab', 'done']:
                for line in rec.bop_ids:
                    if not line._origin.id:
                        raise ValidationError("Tidak boleh menambah baris saat status Approved atau Done.")

    def _notify_success(self, message):
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": "Success!",
                "message": message,
                "type": "success",
            },
        )

    def _notify_error(self, message):
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": "Error!",
                "message": message,
                "type": "danger",
            },
        )

    @api.depends('contract_line_id')
    def compute_sla_delivery(self):
        for record in self:
            record.sla_delivery = record.contract_line_id.sla or 0

    @api.model_create_multi
    def create(self, vals_list):
        # for vals in vals_list:
        #     vals['manifest_no'] = vals['name'] = self.env['ir.sequence'].next_by_code('fleet.do')
        record = super().create(vals_list)
        record._update_po_line_flag()
        # self._check_auto_confirm()
        return record

    def _locked_allowed_fields(self):
        """Fields that may be written even when record is locked.
        - stored computed fields (Odoo writes them on recompute)
        - technical/mail fields that shouldn't block UI
        """
        computed_stored = {
            name for name, f in self._fields.items()
            if f.compute and f.store
        }
        technical = {
            'message_follower_ids', 'message_partner_ids', 'message_ids',
            'activity_ids', 'activity_state', 'activity_exception_decoration',
            'activity_exception_icon', '__last_update', 'display_name', 'bop_paid'
        }
        return computed_stored | technical

    def write(self, vals):
        _logger.info(f"Write Vals => {vals}")
        if "status_do" in vals:
            if self.is_already_do_match:
                self.status_do = 'DO Match'

        allowed_when_locked = self._locked_allowed_fields()
        illegal = set(vals.keys()) - allowed_when_locked
        if (self.state == 'done' or self.status_delivery == 'good_receive') and illegal:
            raise UserError("DO sudah Good Received / Done, Tidak boleh ada Perubahan lagi")
        res = super().write(vals)

        if "po_line_ids" in vals:
            self._update_po_line_flag()
            self._update_vehicle_actual_value()
            for record in self:
                # Make sure Status DO in Valid Value
                removed_ids = []
                added_ids = []

                for cmd in vals['po_line_ids']:
                    if cmd[0] == 3:  # unlink from relation only
                        removed_ids.append(cmd[1])
                    elif cmd[0] == 6:  # replace all
                        removed_ids = list(set(record.po_line_ids.ids) - set(cmd[2]))
                    elif cmd[0] == 5:  # remove all
                        removed_ids = record.po_line_ids.ids

                if removed_ids:
                    removed_lines = self.env['sale.order.line'].browse(removed_ids)
                    if any(rl.is_header for rl in removed_lines):
                        remaining_lines = record.po_line_ids - removed_lines
                        if not any(rl.is_header for rl in remaining_lines):
                            raise ValidationError("Header harus ada satu!")
                # if not record.po_line_ids.filtered(lambda head: head.is_header == True):
                #     raise ValidationError("Header harus ada satu!")

        # if "state" in vals or 'is_match_po' in vals or 'is_match_do' in vals or 'attach_doc_complete' in vals:
        #     self._check_auto_confirm()
        if "state" in vals and vals["state"] == "to_approve":
            for rec in self:
                if rec.category_id.is_shipment:
                    continue
                if rec.vehicle_id and rec.vehicle_id.asset_type == 'asset':
                    driver = rec.vehicle_id.driver_id
                    if not driver:
                        raise ValidationError("Mohon untuk memilih driver terlebih dahulu!")
                        
                    rec.transfer_to = driver.id if driver else False

                    bank = driver.bank_name_ids
                    if not bank:
                        raise ValidationError("Driver belum memiliki data rekening. Mohon lengkapi terlebih dahulu!")

                    bank = bank[0]
                    rec.rekening_number = bank.acc_number
                    rec.rekening_name = bank.acc_holder_name
                    rec.rekening_bank = bank.bank_id.name
                    
        if "state" in vals and vals["state"] == "done":
            _logger.info(f'on write fleet.do => line length {len(self.po_line_ids)} {self.po_line_ids}')
            self._update_actual_target_from_state()
            if self.driver_id:
                self.driver_id.availability = 'Ready'

            for line in self.po_line_ids:
                so = line.order_id
                _logger.info(f"on write fleet.do => SO State {so.id} {so.state}")
                if so.state == 'sale':
                    so.sudo().write({
                        'invoice_status': 'to invoice'
                    })

        return res

    def _update_actual_target_from_state(self):
        _logger = logging.getLogger('oke')
        for do in self:
            total = 0
            for target_line in do.vehicle_id.target_line_ids :
                if target_line.date_is_match(do.date, target_line.year, target_line.month):
                    target_line.actual_target += sum(do.po_line_ids.mapped('price_unit'))

    def _update_vehicle_actual_value(self):
        for do in self:
            total = 0
            fleet_dos = self.env['fleet.do'].search([
                ('vehicle_id', '=', self.vehicle_id.id),
                ('state', '=', 'done'),
            ])
            vehicle_targets = self.env['vehicle.target.line'].search([
                ('vehicle_id', '=', self.vehicle_id.id),
            ])

            for order in fleet_dos:
                order_year_month = order.date.strftime('%Y-%m')
                do_year_month = do.date.strftime('%Y-%m')
                for target_line in vehicle_targets:
                    if target_line.date_is_match(order.date, target_line.year, target_line.month) and (
                            order_year_month == do_year_month):
                        total += sum(order.po_line_ids.mapped('price_unit'))\

            for target_line in do.vehicle_id.target_line_ids:
                if target_line.date_is_match(do.date, target_line.year, target_line.month):
                    target_line.actual_target = total

    def _update_po_line_flag(self):
        """Set flagging di PO Line kalau sudah di-attach ke DO"""
        for do in self:
            po_line = do.po_line_ids
            po_line.write({"do_id": do.id})

            # Kalau ada PO Line yang dicabut dari DO, reset flag-nya
            detached_lines = self.env["sale.order.line"].search([
                ("id", "not in", po_line.ids),
                ("do_id", "=", do.id)
            ])
            if detached_lines:
                detached_lines.write({"do_id": False})

    @api.depends('po_line_ids', 'vehicle_id')
    def compute_access_approval(self):
        for rec in self:
            rec.access_approval = False
            if rec.po_line_ids:
                if rec.state == 'draft' and rec.vehicle_id:
                    rec.access_approval = True
                elif rec.delivery_category_id.name == 'Self Drive':
                    rec.access_approval = True

    @api.depends('driver_id')
    def compute_transfer_to(self):
        for rec in self:
            rec.transfer_to = False
            if rec.vehicle_id:
                if rec.vehicle_id.asset_type == 'asset':
                    driver = rec.vehicle_id.driver_id
                    rec.transfer_to = driver.id
                    bank = driver.bank_ids[:1]  # ambil 1 kalau ada, kalau kosong hasilnya [] (safe)
                    rec.rekening_number = bank.acc_number if bank else False
                    rec.rekening_name = bank.acc_holder_name if bank else False
                    rec.rekening_bank = bank.bank_id.name
                    # rec.rekening_number = driver.bank_ids[0].acc_number
                elif rec.vehicle_id.asset_type == 'vendor':
                    driver = rec.vehicle_id.vichle_ownership
                    if 'ownership_id' in rec.vehicle_id:
                        driver = rec.vehicle.ownership_id
                    rec.transfer_to = driver.id
            elif rec.driver_id:
                driver = rec.driver_id
                rec.transfer_to = driver.id
                bank = driver.bank_ids[:1]  # ambil 1 kalau ada, kalau kosong hasilnya [] (safe)
                rec.rekening_number = bank.acc_number if bank else False
                rec.rekening_name = bank.acc_holder_name if bank else False
                rec.rekening_bank = bank.bank_id.name

    @api.depends('vehicle_id')
    def compute_no_lambung(self):
        for rec in self:
            rec.no_lambung = False
            if rec.vehicle_id:
                rec.no_lambung = rec.vehicle_id.no_lambung

    @api.depends('partner_id')
    def compute_tag_ids(self):
        for rec in self:
            rec.tag_ids = [(5, 0, 0)]
            if rec.partner_id:
                rec.tag_ids = rec.partner_id.category_id.ids

    @api.depends('po_line_ids', 'po_line_ids.qty_unit', 'po_line_ids.qty_tonase', 'po_line_ids.qty_kubikasi', 'category_id',
                 'category_id.min_tonase', 'category_id.max_tonase', 'category_id.min_kubikasi',
                 'category_id.max_kubikasi', 'vehicle_id.vehicle_status', 'driver_id.availability', 'state')
    def compute_status_do(self):
        for rec in self:
            temp_status_do = rec.status_do
            if not rec.is_success_send_to_tms:
                rec.status_do = 'DO Line not Created'
                _logger.info(f"Is Already DO Match: {rec.is_already_do_match}")
                _logger.info(f"Is Already DO Un-Match: {rec.is_already_do_unmatch}")
                if rec.is_already_do_match or temp_status_do == 'DO Match':
                    rec.status_do = 'DO Match'
                if rec.po_line_ids:
                    tonase_line = sum(rec.po_line_ids.mapped('qty_tonase'))
                    kubikasi_line = sum(rec.po_line_ids.mapped('qty_kubikasi'))
                    unit_line = sum(rec.po_line_ids.mapped('qty_unit'))
                    if rec.state != 'draft':
                        if rec.category_id.min_tonase <= tonase_line <= rec.category_id.max_tonase \
                                and rec.category_id.min_kubikasi <= kubikasi_line <= rec.category_id.max_kubikasi \
                                and rec.vehicle_id.vehicle_status == 'ready' \
                                and rec.driver_id.availability in ['Ready', 'On Duty']:
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        elif rec.category_id.is_shipment and unit_line <= rec.category_id.max_unit:
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        elif rec.delivery_category_id.name == 'Self Drive':
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        else:
                            if rec.is_already_do_match:
                                rec.status_do = 'DO Match'
                            elif rec.is_already_do_unmatch:
                                rec.status_do = 'DO Unmatch'
                    elif rec.state == 'draft':
                        if rec.category_id.min_tonase <= tonase_line <= rec.category_id.max_tonase \
                                and rec.category_id.min_kubikasi <= kubikasi_line <= rec.category_id.max_kubikasi \
                                and rec.vehicle_id.vehicle_status == 'ready' \
                                and rec.driver_id.availability == 'Ready':
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        elif rec.category_id.is_shipment and unit_line <= rec.category_id.max_unit:
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        elif rec.delivery_category_id.name == 'Self Drive':
                            rec.status_do = 'DO Draft'
                            if rec.state not in ['draft', 'to_approve', 'cancel']:
                                rec.status_do = 'DO Match'
                        else:
                            if rec.is_already_do_match:
                                rec.status_do = 'DO Match'
                            elif rec.is_already_do_unmatch:
                                rec.status_do = 'DO Unmatch'
            if rec.is_already_do_match:
                rec.status_do = 'DO Match'

    @api.depends('po_line_ids', 'po_line_ids.origin_id')
    def compute_origin(self):
        for rec in self:
            rec.origin_id = False
            if rec.po_line_ids.mapped('origin_id'):
                rec.origin_id = rec.po_line_ids.mapped('origin_id')[0].id

    @api.depends('po_line_ids', 'po_line_ids.destination_id')
    def compute_destination(self):
        for rec in self:
            rec.destination_id = False
            if rec.po_line_ids.mapped('destination_id'):
                rec.destination_id = rec.po_line_ids.mapped('destination_id')[0].id

    @api.depends('nominal', 'bop_driver_used')
    def compute_prev_nominal(self):
        for rec in self:
            if rec.prev_nominal == 0:
                rec.prev_nominal = rec.nominal + rec.bop_driver_used
            else:
                rec.prev_nominal = rec.prev_nominal

    @api.depends('po_line_ids', 'po_line_ids.is_header', 'vehicle_id', 'vehicle_id.asset_type')
    def compute_nominal(self):
        for rec in self:
            po_header = rec.po_line_ids.filtered(lambda head: head.is_header == True)
            if len(rec.po_line_ids.mapped('order_id')) > 1:
                max_bop = max(rec.po_line_ids.mapped('bop'))
                nominal = max_bop
            elif len(rec.po_line_ids.mapped('order_id')) == 1:
                nominal = sum(rec.po_line_ids.mapped('bop'))
            else:
                nominal = 0.0

            if rec.vehicle_id.asset_type and rec.vehicle_id.asset_type.lower() == 'vendor':
                nominal = 0
            else:
                if rec.sale_id:
                    nominal = sum(rec.sale_id.order_line.mapped('bop'))

            rec.nominal = float_round(nominal, precision_digits=0, rounding_method='UP')

    # @api.depends('vehicle_id.x_studio_total_hpp', 'vehicle_id.x_studio_total_revenue')
    # def compute_margin(self):
    #     for rec in self:
    #         rec.margin = 0
    #         rec.margin_percentage = 0
    #         if rec.hpp and rec.revenue:
    #             rec.margin = rec.revenue - rec.hpp
    #             rec.margin_percentage = rec.margin / rec.revenue

    @api.depends('bop_ids', 'bop_ids.amount_paid', 'nominal', 'vehicle_id', 'vehicle_id.asset_type')
    def compute_bop(self):
        for rec in self:
            if rec.bop_ids:
                # rec.bop_paid = sum(rec.bop_ids.mapped('amount_paid'))
                rec.bop_paid = sum(rec.bop_ids.filtered_domain([('is_additional_cost', '=', False)])
                         .mapped('amount_paid') or [0.0])
            else:
                rec.bop_paid = 0

            if rec.nominal:
                # bop_paid = sum(
                #     rec.bop_ids.filtered(lambda bop: bop.state and bop.state in (['approved_by_kacab'])).mapped(
                #         'amount_paid'))

                # bop_paid = sum(rec.bop_ids.mapped('amount_paid'))
                bop_paid = sum(rec.bop_ids.filtered_domain([('is_additional_cost', '=', False)])
                         .mapped('amount_paid') or [0.0])
                do_nominal = float_round(rec.nominal, precision_digits=0, rounding_method='UP')
                do_bop_paid = float_round(bop_paid, precision_digits=0, rounding_method='UP')
                rec.bop_unpaid = do_nominal - do_bop_paid
                rec.bop_percentage_paid = do_bop_paid / do_nominal
            else:
                rec.bop_unpaid = 0
                rec.bop_percentage_paid = 0

            # total_paid = sum(rec.bop_ids.mapped('amount_paid'))

            # _logger.info(f"On Compute BOP => {rec}")
            # total_paid = sum(
            #     rec.bop_ids.filtered(lambda bop: bop.state and bop.state in (['approved_by_kacab'])).mapped('amount_paid'))
            #
            # if total_paid > rec.nominal:
            #     raise ValidationError("Total Paid Amount dari BOP tidak boleh melebihi Summary BOP!")

            if rec.vehicle_id.asset_type and rec.vehicle_id.asset_type.lower() == 'vendor' and not rec.product_category_id.name == 'VLI':
                rec.bop_paid = 0
                rec.bop_unpaid = 0
                rec.bop_percentage_paid = 0
                for line in rec.po_line_ids:
                    line.bop = 0
            else:
                is_selfdrive = bool(rec.delivery_category_id) and rec.delivery_category_id.name == 'Self Drive'
                is_vli = bool(rec.product_category_id) and rec.product_category_id.name == 'VLI'
                has_shipment = any(rec.po_line_ids.mapped('product_id.vehicle_category_id.is_shipment'))
                for line in rec.po_line_ids:
                    if line.bop == 0 and not (is_selfdrive or has_shipment or is_vli):
                        formula_bop = self.env['fleet.bop'].search(
                            [
                                ("customer", "=", line.order_id.partner_id.id),
                                ("origin_id", "=", line.origin_id.id),
                                ("destination_id", "=", line.destination_id.id),
                                ("category_id", "=", line.product_id.vehicle_category_id.id),
                            ],
                            limit=1,
                        )
                        if formula_bop:
                            line.bop = formula_bop.total_bop

    @api.depends('driver_id')
    def action_request_approval(self):

        # if self.create_uid.id != self.env.user.id:
        #     raise UserError("Anda tidak dapat melakukan pengajuan ini")

        self.state = 'to_approve'
        on_book = self.env['fleet.vehicle.status'].search([('name_description', 'ilike', 'On Book')], limit=1)
        self.vehicle_id.write({'last_status_description_id': on_book.id})
        for rec in self:
            if rec.driver_id:
                self.driver_id.write({'availability': 'On Duty'})

        review_state = 'approved_operation_spv'
        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            ('model', '=', self._name)
        ], limit=1)

        review = self.env['tier.review'].create({
            'res_id': self.id,
            'model': self._name,
            'name': "Request to Operation SPV",
            'review_state': review_state,
            'status': 'pending',
            'requested_by': self.env.user.id,
            'comment': "Request to Operation SPV",
            'definition_id': tier_definition.id,
            'company_id': self.env.user.company_id.id,
            'sequence': 1,
        })

        reviewer = tier_definition.reviewer_id
        if not reviewer or not reviewer.active:
            raise UserError(_("Reviewer belum diisi / non-aktif di Tier Definition."))

        if 'reviewer_id' in review._fields:
            review.reviewer_id = reviewer.id

        # Subscribe ke chatter biar dapat update
        # self.message_subscribe(partner_ids=[reviewer.partner_id.id])

        todo_type = self.env.ref('mail.mail_activity_data_todo')
        Activity = self.env['mail.activity'].sudo()
        existing = Activity.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', todo_type.id),
            ('user_id', '=', reviewer.id),
            ('date_done', '=', False),
        ], limit=1)

        if not existing:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=reviewer.id,
                summary=_("Tier Approval: %s") % review_state,
                note=_("Mohon approval untuk %s.") % (self.display_name,),
                date_deadline=fields.Date.today(),
            )

        return True

    def _format_plan_time(self, plan_time):
        """Format plan_time to YYYY-MM-DD HH:mm:ss format or return empty string."""
        if not plan_time:
            return ""

        try:
            # If plan_time is already a datetime object
            if hasattr(plan_time, 'strftime'):
                return plan_time.strftime("%Y-%m-%d %H:%M:%S")

            # If plan_time is a string, try to parse it
            if isinstance(plan_time, str):
                # Try parsing common datetime formats
                try:
                    dt = datetime.fromisoformat(plan_time.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    # If parsing fails, return empty string
                    return ""

            return ""
        except:
            return ""

    def action_update_post_do(self):
        self.ensure_one()

        if self.delivery_category_id.name == 'Self Drive':
            return

        is_from_btn_action = self.env.context.get('is_from_btn_action')
        # Check if method is called from button action
        if is_from_btn_action:
            # Check if all lines have no_surat_jalan
            lines_without_sj = self.po_line_ids.filtered(lambda l: not l.no_surat_jalan)

            # If all lines don't have no_surat_jalan, show popup
            if len(lines_without_sj) == len(self.po_line_ids):
                raise UserError("No Surat Jalan wajib di isi terlebih dahulu")

        vehicle = self.vehicle_id
        is_return_to_pool = vehicle.vehicle_status.lower() == 'on_return' and vehicle.last_status_description_id.name_description.lower() == 'on the way pull'
        do_date = datetime.fromisoformat(self.date.isoformat())
        longest_lines = self.po_line_ids.filtered(
            lambda l: (l.distance or 0) == max(self.po_line_ids.mapped('distance') or [0])
        )
        cpty_muatan = {
            'qty_tonase': sum(self.po_line_ids.mapped('qty_tonase')),
            'qty_kubikasi': sum(self.po_line_ids.mapped('qty_kubikasi')),
        }
        cpty_muatan_value = max([
            cpty_muatan['qty_tonase'],
            cpty_muatan['qty_kubikasi'],
        ])
        formatted_data = {
            'no_do': self.name,
            'tgl_do': do_date.strftime("%Y-%m-%d %H:%M:%S"),
            'car_plate': vehicle.license_plate,
            'geo_asal': [
                {
                    'code': self.geofence_loading_id.geo_code,
                    'plan_time': self._format_plan_time(self.plan_loading_time) if self.plan_loading_time else "",
                    'geo_label': self.geofence_loading_id.geo_nm,
                    'stop_num': '',
                }
                for line in longest_lines.filtered(lambda x: x.is_header == True)
            ],
            'geo_tujuan': [
                {
                    'code': self.geofence_unloading_id.geo_code,
                    'no_sj': line.no_surat_jalan,
                    'plan_unloading': self._format_plan_time(self.plan_unloading_time) if self.plan_unloading_time else "",
                    'geo_label': self.geofence_unloading_id.geo_nm,
                    'stop_num': '',
                }
                for line in self.po_line_ids.filtered(lambda x: x.is_header == True)
            ],
            'shipment': {
                'tarif_angkut': round(sum(
                    self.po_line_ids.filtered(
                        lambda l: l.product_id.categ_id.complete_name.lower() != 'transporter / biaya tambahan'
                    ).mapped('price_unit')
                )), # Sum Price Unit yang bukan biaya tambahan
                'uang_jalan': round(longest_lines[0].bop),
                'cpty_muatan': math.floor(float_round(cpty_muatan_value, 2)),
            }
        }

        uang_tambahan = math.floor(float_round(
            sum(
                self.po_line_ids.filtered(
                    lambda l: l.product_id.categ_id.complete_name.lower() == 'transporter / biaya tambahan'
                ).mapped('price_unit')
            ), 2
        ))

        if is_from_btn_action and self.do_id:
            formatted_data['do_id'] = self.do_id

        formatted_data['opsi_complete'] = 'Return to Pool / Asal' if is_return_to_pool else ''
        formatted_data['shipment']['jns_satuan'] = 'ton' if cpty_muatan_value == cpty_muatan['qty_tonase'] else 'm3'
        formatted_data['shipment']['uang_tambahan'] = uang_tambahan if uang_tambahan and uang_tambahan > 0 else 0
        result: bool = self.post_data_to_TMS(data=formatted_data)
        if is_from_btn_action:
            if result:
                self._notify_success("Successfully update data to TMS")
            else:
                self._notify_error("An error occurred. Data failed to be sent to TMS")

        return result

    @api.model
    def post_data_to_TMS(self, data={}):
        """Method yang akan dijalankan ketika diapprove kacab"""
        try:
            _logger.info("=== DO ===> ", data)
            # URL dari ir.config_parameter
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            base_external_api_url = base_url
            endpoint = "https://vtsapi.easygo-gps.co.id/api/do/AddOrUpdateDOV1ByGeoCode"

            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "token": "55AEED3BF70241F8BD95EAB1DB2DEF67",
            }
            params = data
            _logger.info(f"=== DO ===> params {params}")
            # Melakukan HTTP request
            response = requests.post(endpoint, headers=headers, json=params)

            # Log response
            _logger.info(f"=== DO ===> Endpoint hit successful: {endpoint} -> {response.status_code} -> params {params}")
            _logger.info(f"=== DO ===> Response: {response.text}")

            # Check if response has content before parsing it as JSON
            res_data = None
            if response.text.strip():
                try:
                    external_data = response.json()
                    _logger.info(f"=== DO ===> Parse JSON: {external_data}")
                    res_data = external_data.get('Data', [])
                    _logger.info(f"=== DO ===> DATA: {res_data}")
                except ValueError as json_err:
                    _logger.warning(f"=== DO ===> JSON parsing error: {str(json_err)}")
                    _logger.warning(f"=== DO ===> Response content: {response.text}")
            else:
                _logger.warning("=== DO ===> Empty response received")

            # Consider success based on HTTP status code instead of JSON parsing
            if response.status_code in (200, 201, 202, 204):
                self.is_success_send_to_tms = True
                self.do_id = res_data["do_id"]
                return True
            else:
                _logger.warning(f"=== DO ===> Unsuccessful status code: {response.status_code}")
                self.is_success_send_to_tms = False
                return False

        except Exception as e:
            _logger.error(f"=== DO ===> Error hitting endpoint: {str(e)}")
            self.is_success_send_to_tms = False
            return False

    def action_approve_operation_spv(self):
        if self.state != 'to_approve':
            raise UserError("Action not allowed from current state.")
        
        cur_def = self._tier_def('approved_operation_spv')
        if not cur_def:
            raise UserError(_("Tier Definition untuk state %s tidak ditemukan.") % 'Supervisor')
        if getattr(cur_def, 'reviewer_id', False) and cur_def.reviewer_id != self.env.user:
            raise UserError(_("Anda bukan reviewer untuk tahap ini."))

        self._close_my_todo_activity()

        self.approval_date_operation_spv = fields.Date.today()
        self.approval_by_operation_spv = self.env.user.id

        if self.is_lms(self.env.company.portfolio_id.name):
            for line in self.po_line_ids:
                analytic_account = None

                if str(self.product_category_id.name).upper() == 'VLI':
                    analytic_account = self.env['account.move']._get_or_create_analytic_account((
                        self.category_id.name,
                        '',
                        '',
                        self.product_category_id.name,
                        self.product_category_id.name,
                        self.category_id.name
                    ))
                else:
                    analytic_account = self.env['account.move']._get_or_create_analytic_account((
                        self.vehicle_id.vehicle_name,
                        '',
                        '',
                        self.vehicle_id.no_lambung,
                        self.vehicle_id.product_category_id.name,
                        self.vehicle_id.category_id.name
                    ))

                if analytic_account:
                    analytic_distribution = {str(analytic_account.id): 100}
                    line.write({
                        'analytic_distribution': analytic_distribution
                    })
                    line.can_update_analytic_distribution_via_so = False
                    
                    self.vehicle_id.forecast_status_ready = 'On Book'

        self.generate_po()

        self._update_tier_review('approved_operation_spv', 'Approved by Operation SPV')
        
        # === NEXT TIER ===
        next_state = 'approved_cashier'
        nxt_def = self._tier_def(next_state)
        if nxt_def:
            review = self._create_tier_review(next_state, 'Request to Cashier')
            reviewer = getattr(nxt_def, 'reviewer_id', False)
            if reviewer:
                self.current_reviewer_id = reviewer.id
                self._schedule_todo_for(
                    reviewer,
                    summary=_("Tier Approval: %s") % next_state,
                    note=_("Mohon approval untuk %s.") % (self.display_name,)
                )
            self.state = 'approved_operation_spv'
        else:
            self.state = 'approved_operation_spv'

        self.message_post(body=_("Approved by %s (Operation Supervisor)") % self.env.user.name)
        return True

    def action_approve_cashier(self):
        if self.state != 'approved_operation_spv':
            raise UserError("Action not allowed from current state.")
            
        cur_def = self._tier_def('approved_cashier')
        if not cur_def:
            raise UserError(_("Tier Definition untuk state %s tidak ditemukan.") % 'approved_chasier')
        if getattr(cur_def, 'reviewer_id', False) and cur_def.reviewer_id != self.env.user:
            raise UserError(_("Anda bukan reviewer untuk tahap ini."))
            
        self._close_my_todo_activity()

        self._update_tier_review('approved_cashier', 'Approved by Operation Cashier')

        # if self.category_id and self.category_id.name.lower() != 'self drive':
        #     if self.vehicle_id and self.vehicle_id.asset_type == 'asset':
        #         if not self.bop_state:
        #             raise UserError(_("Status BOP wajib diisi"))

        # prioritas: baris yang men-trigger, fallback ke yang pertama
        bop_line = False
        active_bop_line_id = self.env.context.get('active_bop_line_id')
        if active_bop_line_id:
            candidate = self.env['bop.line'].browse(active_bop_line_id)
            if candidate and candidate.fleet_do_id.id == self.id:
                bop_line = candidate
        if not bop_line:
            bop_line = self.env['bop.line'].search([('fleet_do_id', '=', self.id)], limit=1)
        if not bop_line:
            raise UserError("Mohon lengkapi data BOP terlebih dahulu pada tab BOP")

        bop_line.write({
            'state': 'approved_cashier'
        })

        self.approval_date_cashier = fields.Date.today()
        self.approval_by_cashier = self.env.user.id
        self.state = 'approved_cashier'
        
        # === NEXT TIER ===
        next_state = 'approved_adh'
        nxt_def = self._tier_def(next_state)
        if nxt_def:
            review = self._create_tier_review(next_state, 'Request to Administration Head')
            reviewer = getattr(nxt_def, 'reviewer_id', False)
            if reviewer:
                self.current_reviewer_id = reviewer.id
                self._schedule_todo_for(
                    reviewer,
                    summary=_("Tier Approval: %s") % next_state,
                    note=_("Mohon approval untuk %s.") % (self.display_name,)
                )
            self.state = 'approved_cashier'
        else:
            self.state = 'approved_cashier'

        self.message_post(body=_("Approved by %s (Operation Cashier)") % self.env.user.name)
        return True

    def action_approve_adh(self):
        if self.state != 'approved_cashier':
            raise UserError("Action not allowed from current state.")
            
        cur_def = self._tier_def('approved_adh')
        if not cur_def:
            raise UserError(_("Tier Definition untuk state %s tidak ditemukan.") % 'Administration Head')
        if getattr(cur_def, 'reviewer_id', False) and cur_def.reviewer_id != self.env.user:
            raise UserError(_("Anda bukan reviewer untuk tahap ini."))
            
        self._close_my_todo_activity()

        self.approval_date_adh = fields.Date.today()
        self.approval_by_adh = self.env.user.id
        self.state = 'approved_adh'

        bop_line = self.env['bop.line'].search([('fleet_do_id', '=', self.id)])
        bop_line.write({
            'state': 'approved_adh'
        })

        self._update_tier_review('approved_adh', 'Approved by Administration Head')
        
        # === NEXT TIER ===
        next_state = 'approved_by_kacab'
        nxt_def = self._tier_def(next_state)
        if nxt_def:
            review = self._create_tier_review(next_state, 'Request to Kepala Cabang')
            reviewer = getattr(nxt_def, 'reviewer_id', False)
            if reviewer:
                self.current_reviewer_id = reviewer.id
                self._schedule_todo_for(
                    reviewer,
                    summary=_("Tier Approval: %s") % next_state,
                    note=_("Mohon approval untuk %s.") % (self.display_name,)
                )
            self.state = 'approved_adh'
        else:
            self.state = 'approved_adh'

        self.message_post(body=_("Approved by %s (Administration Head)") % self.env.user.name)
        return True

    def action_approve_by_kacab(self):
        self.ensure_one()
        if self.state != 'approved_adh':
            raise UserError("Action not allowed from current state.")
        if not self.geofence_loading_id or not self.geofence_unloading_id:
            raise UserError("Geofence Loading and Geofence Unloading must be filled in.")

        cur_def = self._tier_def('approved_by_kacab')
        if not cur_def:
            raise UserError(_("Tier Definition untuk state %s tidak ditemukan.") % 'approved_by_kacab')
        if getattr(cur_def, 'reviewer_id', False) and cur_def.reviewer_id != self.env.user:
            raise UserError(_("Anda bukan reviewer untuk tahap ini."))
            
        self._close_my_todo_activity()
        
        ### ℹ️ selain vehicle dengan type = Aset tidak akan dikirim ke TMS
        if str(self.vehicle_id.asset_type).lower() == 'asset':
            res = self.action_update_post_do()
            self._notify_success("Successfully approve and send data to TMS")

        review_state = 'approved_by_kacab'
        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            ('reviewer_id', '=', self.env.user.id), #todo: ini masih 1 user
            ('model', '=', self._name)
        ], limit=1)

        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")

        self._update_tier_review('approved_by_kacab', 'Approved by Kepala Cabang')

        # if res:
        self.action_update_status_do(self)
        # else:
        #     self._notify_error("An error occurred. Data failed to be sent to TMS")

        self.approval_date_by_kacab = fields.Date.today()
        self.approval_by_kacab = self.env.user.id
        self.state = 'approved_by_kacab'

        bop_line = self.env['bop.line'].search([('fleet_do_id', '=', self.id)])
        bop_line.write({
            'state': 'approved_by_kacab'
        })
            
    def action_update_status_do(self, data, start_str=None, stop_str=None, fleet_do_id=None):
        try:
            _logger.info("=== DO ===> ", data)
            # URL dari ir.config_parameter
            endpoint = "https://vtsapi.easygo-gps.co.id/api/do/report"

            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "token": "55AEED3BF70241F8BD95EAB1DB2DEF67",
            }
            
            # default: range hari ini
            if not start_str or not stop_str:
                target_date = fields.Date.context_today(self)
                start_dt = datetime.combine(target_date, time(0, 0, 0))
                stop_dt  = datetime.combine(target_date, time(23, 59, 59))
                start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                stop_str  = stop_dt.strftime('%Y-%m-%d %H:%M:%S')
                
            name_do = str(data.name)
            if not fleet_do_id:
                name_do = str(fleet_do_id.name)
            
            formatted_data = {
                # 'start_time': "2025-08-27 00:00:00",
                # 'stop_time': "2025-08-27 23:59:59",
                # 'no_do': ["DO/00010/VLI/8/2025"],
                'start_time': start_str,
                'stop_time': stop_str,
                'no_do': name_do,
                # 'do_id': [data.do_id],
                # 'lstNoPOL': [data.vehicle_id.license_plate],
                # 'lstGeoCodeTujuan': [data.geofence_unloading_id.geo_code],
                # 'no_do': [data.name],
                # 'do_id': [data.do_id],
                # 'status_do': 0,
            }
            
            params = formatted_data
            _logger.info(f"=== DO ===> params {params}")
            # Melakukan HTTP request
            response = requests.post(endpoint, headers=headers, json=params)

            # Log response
            _logger.info(f"=== DO ===> Endpoint hit successful: {endpoint} -> {response.status_code} -> params {params}")
            _logger.info(f"=== DO ===> Response: {response.text}")

            # Check if response has content before parsing it as JSON
            res_data = None
            if response.text.strip():
                try:
                    external_data = response.json()
                    _logger.info(f"=== DO ===> Parse JSON: {external_data}")
                    res_data = external_data.get('Data', [])
                    _logger.info(f"=== DO ===> DATA: {res_data}")
                except ValueError as json_err:
                    _logger.warning(f"=== DO ===> JSON parsing error: {str(json_err)}")
                    _logger.warning(f"=== DO ===> Response content: {response.text}")
            else:
                _logger.warning("=== DO ===> Empty response received")

            if response.status_code in (200, 201, 202, 204):
                status_do = None
                if isinstance(res_data, dict):
                    status_do = res_data.get('status_do')
                elif isinstance(res_data, list) and res_data and isinstance(res_data[0], dict):
                    status_do = res_data[0].get('status_do')

                mapping = {
                    0: ('ready',    'On Book'),          # In Used
                    1: ('on_going', 'Loading'),          # In Asal
                    2: ('on_going', 'On Delivery'),      # OTW  Tujuan
                    3: ('on_going', 'Unloading'),        # In Tujuan
                    4: ('on_return','On The Way Pool'),  # Out Tujuan
                }

                if status_do in mapping:
                    
                    if data.vehicle_id:
                        # update tab trigger available
                        if status_do == 2:
                            data.vehicle_id.geofence_checkpoint = False
                            data.vehicle_id.driver_confirmation = False
                            data.vehicle_id.plan_armada_confirmation = False
                        if status_do == 4:
                            data.vehicle_id.geofence_checkpoint = True
                            
                        vehicle_status, last_label = mapping[status_do]
                        veh = data.vehicle_id
                        vals = {}

                        # selalu set vehicle_status (Selection)
                        vals['vehicle_status'] = vehicle_status
                        last_status_description_id = self.env['fleet.vehicle.status'].search([('name_description', 'ilike', last_label)], limit=1)
                        vals['last_status_description_id'] = last_status_description_id
                        
                        if vals:
                            veh.write(vals)
                        
                    if (response.headers.get('Content-Type','').lower().startswith('application/json')):
                        try:
                            ext = response.json()
                        except ValueError:
                            _logger.warning("Body bukan JSON valid: %r", (response.text or "")[:500])
                            ext = {}
                    else:
                        _logger.warning("Content-Type bukan JSON: %s", response.headers.get('Content-Type'))
                        ext = {}

                    # update delivery document (DO)
                    status_map = {
                        0: 'draft',
                        1: 'on_going',
                        2: 'on_going',
                        3: 'on_going',
                        4: 'on_return',
                    }

                    new_status = status_map.get(status_do, 'draft')

                    # lebih aman pakai write supaya langsung commit ke DB
                    data.write({'status_delivery': new_status})

                    # sinkron ke Sale Order (jika ada dan field-nya tersedia)
                    # if data.sale_id and 'status_delivery' in self.env['sale.order']._fields:
                    #     data.sale_id.write({'status_delivery': new_status})
                    
                    sol = self.env['sale.order.line'].search([('do_id', '=', data.id)])
                    sos = sol.mapped('order_id')
                    if sos:
                        sos.write({'status_delivery': new_status})
                        
                    # Simpan/Update baris report (asal & tujuan)
                    self._upsert_report_from_api(ext)

                return True

            else:
                _logger.warning(f"=== DO ===> Unsuccessful status code: {response.status_code}")
                return False

        except Exception as e:
            _logger.error(f"=== DO ===> Error hitting endpoint: {str(e)}")
            return False

    def action_reject(self):
        reason = self.env.context.get('reject_reason')
        skip_comment = self.env.context.get('skip_comment_check')
        if not reason and not skip_comment and any(rec._is_comment_required_for_current_tier() for rec in self):
            return self._open_reject_wizard()

        for rec in self:

            if rec.state in ['approved_operation_spv', 'approved_cashier', 'approved_adh', 'approved_by_kacab']:
                if hasattr(rec, '_reject_tier_state'):
                    rec._reject_tier_state()

            review_state = _REVIEW_TARGET_BY_STATE.get(rec.state)
            if review_state:
                rec._reject_tier_review(review_state, rec._label_for_state(review_state), reason=reason)

            rec._close_all_todo_safe()

            rec.reject_by = self.env.user.id
            rec.reject_date = fields.Date.today()
            rec.state = 'cancel'

            ready_to_use = rec.env['fleet.vehicle.status'].search([('name_description', 'ilike', 'Ready for Use')],
                                                                  limit=1)
            if ready_to_use and rec.vehicle_id:
                rec.vehicle_id.write({
                    'last_status_description_id': ready_to_use.id,
                    'forecast_status_ready': 'Ready for Use',
                })
            if rec.driver_id:
                rec.driver_id.write({'availability': 'Ready'})

            body = _("Rejected by %s") % self.env.user.name
            if reason:
                body += _("<br/><b>Reason:</b> %s") % reason
            if reason and body:
                rec.reject_note = reason

            rec.message_post(body=body)

        return True

    # def action_confirm(self):
    #     if self.state != 'approved_by_kacab':
    #         raise UserError("Action not allowed from current state.")
    #
    #     if not self.status_do == 'DO Match':
    #         raise ValidationError(_("Please fill Nomer Surat Jalan in DO Line!"))
    #
    #     debit_account_id = self.env['account.account'].search([('code', '=', 69000000), ('company_id', 'in', [self.env.user.company_id.parent_id.id, self.env.user.company_id.id])], limit=1)
    #     credit_account_id = self.env['account.account'].search([('code', '=', 11120004), ('company_id', 'in', [self.env.user.company_id.parent_id.id, self.env.user.company_id.id])], limit=1)
    #
    #     if not debit_account_id or not credit_account_id:
    #         raise ValueError("Akun debit dg code 69000000 atau akun kredit dg code 11120004 tidak ada")
    #
    #     journal = self.env['account.journal'].search([
    #         ('type', '=', 'sale'),
    #         ('company_id', '=', self.env.user.company_id.id)
    #     ], limit=1)
    #
    #     move_vals = {
    #         'move_type': 'entry',
    #         'partner_id': self.partner_id.id,
    #         'ref': self.name,
    #         'journal_id': journal.id, #self.bank_cash.id,
    #         'date': fields.Date.today(),
    #         'company_id': self.env.user.company_id.id,
    #         'line_ids': [
    #             (0, 0, {
    #                 'account_id': debit_account_id.id,
    #                 'partner_id': self.partner_id.id,
    #                 'debit': self.nominal,
    #                 'credit': 0.0,
    #                 'name': self.vehicle_id.display_name,
    #                 'currency_id': self.env.user.company_id.currency_id.id
    #             }),
    #             (0, 0, {
    #                 'account_id': credit_account_id.id,
    #                 'partner_id': self.partner_id.id,
    #                 'debit': 0.0,
    #                 'credit': self.nominal,
    #                 'name': self.vehicle_id.display_name,
    #                 'currency_id': self.env.user.company_id.currency_id.id
    #             }),
    #         ],
    #     }
    #
    #     move_id = self.env['account.move'].create(move_vals)
    #     move_id.fleet_id = self.id
    #     self.state = 'done'

    # @api.onchange('is_match_do', 'is_match_po', 'attach_doc_complete')
    # def compute_status_document(self):
    #     for rec in self:
    #         if rec.is_match_do and rec.is_match_po and rec.attach_doc_complete and not rec.status_locked:
    #             rec.status_document_status = 'Good Receive'
    #         else :
    #             rec.status_document_status = 'Document Incompleted'

    # def _check_auto_confirm(self):
    #     for rec in self:
    #         if rec.is_match_do and rec.is_match_po and rec.attach_doc_complete and not rec.status_locked:
    #             rec.status_locked = True
    #             rec.status_document_status = 'Good Receive'
    #             rec.state = 'done'

                # # change status
                # vehicle = rec.vehicle_id
                # vehicle.vehicle_status = 'ready'
                #
                # status = self.env['fleet.vehicle.status'].search([
                #     ('name_description', 'ilike', 'Ready for Use')
                # ], limit=1)
                
                # if status:
                #     vehicle.last_status_description_id = status.id
                
                # if rec.vehicle_id:
                #     rec.vehicle_id.driver_confirmation = True
                    
                # change status dirver
                # driver = rec.driver_id
                # driver.availability = 'Ready'

    # @api.depends('nominal', 'revenue')
    # def compute_bop_percentage(self):
    #     for record in self:
    #         if record.revenue:
    #             record.bop_percentage = round((record.nominal / record.revenue) * 100, 2)
    #         else:
    #             record.bop_percentage = 0.0

    # @api.depends('bop_percentage')
    # def compute_bop_percentage_display(self):
    #     for record in self:
    #         record.bop_percentage_display = f"{record.bop_percentage:.2f}%"

    @api.depends('po_line_ids.qty_tonase', 'po_line_ids.qty_kubikasi')
    def _compute_volume(self):
        for rec in self:
            rec.tonase_line = sum(rec.po_line_ids.mapped('qty_tonase'))
            rec.kubikasi_line = sum(rec.po_line_ids.mapped('qty_kubikasi'))

    @api.depends('state')
    def _compute_review_ids_filtered(self):
        for record in self:
            allowed_states = [
                'to_approve',
                'approved_operation_spv',
                'approved_cashier',
                'approved_adh',
                'approved_by_kacab',
                'done',
                'cancel'

            ]
            record.review_ids = self.env['tier.review'].search([
                ('res_id', '=', record.id),
                ('model', '=', record._name),
                # ('review_state', '=', record.state),
                ('review_state', 'in', allowed_states),
            ])

    def _create_tier_review(self, review_state, approval_label):
        self.ensure_one()
        tdef = self._tier_def(review_state)
        if not tdef:
            raise UserError(_("Tier Definition untuk %s tidak ditemukan.") % review_state)


        # tier_definition = self.env['tier.definition'].search([
        #     ('review_state', '=', review_state),
        #     ('reviewer_id', '=', self.env.user.id),
        #     ('model', '=', self._name)
        # ], limit=1)

        # if not tier_definition:
        #     raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")

        review = self.env['tier.review'].create({
            'res_id': self.id,
            'model': self._name,
            'name': approval_label,
            'review_state': review_state,
            'status': 'pending',
            'requested_by': self.env.user.id,
            'comment': approval_label,
            'definition_id': tdef.id,
            'company_id': self.env.user.company_id.id,
            'sequence': 1,
        })
        return review

    def _update_tier_review(self, review_state, approval_label):
        self.ensure_one()
        
        tdef = self._tier_def(review_state)
        if not tdef:
            raise UserError(_("Tier Definition untuk %s tidak ditemukan.") % review_state)

        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            # ('reviewer_id', '=', self.env.user.id),
            ('model', '=', self._name)
        ], limit=1)

        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujuii permintaan ini")

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', self._name),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'approved',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
                'comment': approval_label,
            })
        return review

    def _reject_tier_review(self, review_state, approval_label, reason=None):
        self.ensure_one()
        tdef = self._tier_def(review_state)
        if not tdef:
            raise UserError(_("Tier Definition untuk %s tidak ditemukan.") % review_state)

        # tier_definition = self.env['tier.definition'].search([
        #     ('review_state', '=', review_state),
        #     ('model', '=', self._name)
        # ], limit=1)

        # if not tier_definition:
        #     raise UserError("Anda tidak memiliki akses untuk membatalkan permintaan ini")

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', self._name),
            ('definition_id', '=', tdef.id)
        ], order='id desc', limit=1)

        if review:
            vals = {
                'status': 'rejected',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
            }
            if 'comment' in review._fields:
                comment = approval_label
                if reason:
                    comment = f"{approval_label} - {reason}"
                vals['comment'] = comment
            review.write(vals)
            
        # tutup TODO milik reviewer ini
        self._close_my_todo_activity()
        # clear current reviewer (opsional)
        self.current_reviewer_id = False
        self.message_post(body=_("Rejected by %s (%s)") % (self.env.user.name, review_state))
        return True

    @api.onchange('field_that_changes')
    def _onchange_field_that_changes(self):
        if self.vehicle_id:
            # Get the related vehicle target lines - pastikan nama model benar
            target_lines = self.env['vehicle.target.line'].search([
                ('vehicle_id', '=', self.vehicle_id.id)
            ])
            
            if target_lines:
                # Call the compute method on the target lines
                target_lines._compute_actual_target()

    def _reject_tier_state(self):
        self.ensure_one()

        state_mapping = {
            'approved_operation_spv': 'approved_cashier',
            'approved_cashier': 'approved_adh',
            'approved_adh': 'approved_by_kacab',
        }

        status_state = state_mapping.get(self.state)

        tier_definition = False
        if status_state:
            tier_definition = self.env['tier.definition'].search([
                ('review_state', '=', status_state),
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', self._name)
            ], limit=1)

        if not tier_definition:
            raise UserError(f"Anda tidak memiliki akses untuk reject di state ini.")

    # @api.onchange('vehicle_id', 'vehicle_id.asset_type')
    # def _onchange_line_bop(self):
    #     for record in self:
    #         print('record => ', record)
    #         if record.vehicle_id.asset_type and record.vehicle_id.asset_type.lower() == 'vendor':
    #             for line in record.po_line_ids:
    #                 line.bop = 0
    #         else:
    #             for line in record.po_line_ids:
    #                 if line.bop == 0:
    #                     formula_bop = self.env['fleet.bop'].search(
    #                         [
    #                             ("customer", "=", line.order_id.partner_id.id),
    #                             ("origin_id", "=", line.origin_id.id),
    #                             ("destination_id", "=", line.destination_id.id),
    #                             ("category_id", "=", line.product_id.vehicle_category_id.id),
    #                         ],
    #                         limit=1,
    #                     )
    #                     if formula_bop:
    #                         line.bop = formula_bop.total_bop
    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancel"):
                raise UserError('Document can only be deleted if status is Draft or Cancelled.')
        return super().unlink()

    def open_approval_spv_fleet_do_wizard(self):
        active_ids = self.env.context.get('active_ids', [])
        bop_lines = self.env['bop.line'].browse(active_ids)

        fleet_do_ids = bop_lines.mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.spv.fleet.do.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Submit Bulk Approval Delivery Order',
            'context': {
                'default_bop_line_ids': [(6, 0, fleet_do_ids)],
            }
        }

    def open_reject_spv_fleet_do_wizard(self):
        active_ids = self.env.context.get('active_ids', [])
        bop_lines = self.env['fleet.do'].browse(active_ids)

        fleet_do_ids = bop_lines.mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reject.spv.fleet.do.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Submit Bulk Reject Delivery Order',
            'context': {
                'default_bop_line_ids': [(6, 0, fleet_do_ids)],
            }
        }

    @api.depends('purchase_order_id')
    def _compute_has_purchase_order(self):
        for record in self:
            record.has_purchase_order = bool(record.purchase_order_id)

    @api.depends('purchase_order_id')
    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = 1 if record.purchase_order_id else 0

    def action_view_purchase_order(self):
        """Action untuk smart button melihat Purchase Order"""
        self.ensure_one()
        if not self.purchase_order_id:
            return self.action_select_purchase_order()

        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.purchase_order_id.id,
            'target': 'current'
        }

    def action_select_purchase_order(self):
        """Action untuk memilih Purchase Order"""
        self.ensure_one()

        return {
            'name': 'Select Purchase Order',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'target': 'new',
            'domain': [('fleet_do_id', '=', False)],  # Hanya PO yang belum punya Fleet DO
            'context': {
                'search_default_draft': 1,
                'fleet_do_id': self.id
            }
        }

    @api.constrains('purchase_order_id')
    def _check_unique_purchase_order(self):
        """Constraint untuk memastikan PO hanya terhubung ke satu Fleet DO"""
        for record in self:
            if record.purchase_order_id:
                existing = self.search([
                    ('purchase_order_id', '=', record.purchase_order_id.id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        f"Purchase Order {record.purchase_order_id.name} sudah terhubung dengan Fleet DO {existing.name}!"
                    )

    def generate_po(self):
        self.ensure_one()
        if self.vehicle_id.asset_type and str(self.vehicle_id.asset_type).lower() == 'vendor':
            # Get vendor vehicle_ownership from vehicle
            vendor_id = self.vehicle_id.vichle_ownership.id if self.vehicle_id.vichle_ownership else False

            if not vendor_id:
                raise UserError(_("Vehicle does not have a vendor assigned."))

            # Get vendor record
            vendor = self.env['res.partner'].browse(vendor_id)

            # Get default picking type for purchase
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'),
                ('company_id', 'in', self.env.user.company_ids.ids)
            ], limit=1)

            company = self.env.user.company_id
            company_code = company.company_code and company.company_code.strip() or False

            if not company_code:
                raise UserError(_("Company Code perusahaan kosong, silakan isi dulu di Settings."))

            # generate nama PO sesuai aturan company_code
            custom_name = self.env['purchase.order']._generate_fleet_po_name(company_code)

            # Prepare PO values
            po_vals = {
                'name': custom_name,
                'partner_id': vendor_id,
                'currency_id': self.currency_id.id,
                'date_order': fields.Datetime.now(),
                'date_planned': fields.Datetime.now(),
                'company_id': self.env.user.company_id.id,
                'user_id': self.env.user.id,
                'origin': self.name,
                'state': 'draft',
                'picking_type_id': picking_type.id if picking_type else False,
                'priority': '1',
            }

            # Create the Purchase Order using ORM
            purchase_order = self.env['purchase.order'].create(po_vals)

            # Create PO lines if they exist
            print('PO ==> ', purchase_order.id, hasattr(self, 'po_line_ids'))
            if hasattr(self, 'po_line_ids'):
                self._create_po_lines_orm(purchase_order.id)

            # Return the created PO record
            return purchase_order

    def _create_po_lines_orm(self, po_id):
        """Create purchase order lines using ORM based on sale order lines"""

        # Get the purchase order record
        purchase_order = self.env['purchase.order'].browse(po_id)
        is_vli_and_not_self_drive = self.product_category_id.name == 'VLI' and self.delivery_category_id.name != 'Self Drive'
        filtered_lines = self.po_line_ids.filtered(lambda x: x.id_contract != False) if is_vli_and_not_self_drive else self.po_line_ids

        for line in filtered_lines:
            product = line.product_id
            if product:
                # Get vendor for currency and pricing
                vendor = self.vehicle_id.vichle_ownership
                price_unit = line.price_unit
                is_tp_truck_product = str(product.vehicle_category_id.product_category_id.name).lower() in ('transporter', 'trucking')
                is_transporter = str(product.vehicle_category_id.product_category_id.name).lower() == 'transporter'

                # # Calculate price based on vendor pricelist or product cost
                # price_unit = product.standard_price or 0.0
                #
                # # Get supplier info for better pricing
                # supplier_info = self.env['product.supplierinfo'].search([
                #     ('product_tmpl_id', '=', product.product_tmpl_id.id),
                #     ('partner_id', '=', vendor.id)
                # ], limit=1)
                #
                # if supplier_info:
                #     price_unit = supplier_info.price or price_unit
                analytic_account = self.env['account.move']._get_or_create_analytic_account((self.vehicle_id.vehicle_name, '', '', self.vehicle_id.no_lambung, self.vehicle_id.product_category_id.name, self.vehicle_id.category_id.name))
                analytic_distribution = None
                if analytic_account:
                    analytic_distribution = {str(analytic_account.id): 100}

                is_shipment_ro_ro = (
                    str(product.categ_id.name).lower() == 'vli'
                    and 'ro-ro' in str(product.vehicle_category_id.name).lower()
                )

                is_vendor_asset = self.asset_type == 'vendor'
                price_unit_value = line.bop
                if is_tp_truck_product and not is_vendor_asset:
                    price_unit_value = product.standard_price
                if is_shipment_ro_ro or (is_transporter and is_vendor_asset) or is_vendor_asset:
                    price_unit_value = sum(product.seller_ids.filtered(
                        lambda x: x.partner_id.id == purchase_order.partner_id.id
                    ).mapped('price'))

                # Prepare PO line values
                po_line_vals = {
                    'order_id': po_id,
                    'name': line.name or product.name,
                    'sequence': line.sequence,
                    'product_id': product.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': price_unit_value,
                    'date_planned': fields.Datetime.now(),
                    'display_type': False,  # False for regular product lines
                }

                if line.analytic_distribution:
                    po_line_vals['analytic_distribution'] = line.analytic_distribution
                else:
                    po_line_vals['analytic_distribution'] = analytic_distribution

                # Create the PO line using ORM
                po_line = self.env['purchase.order.line'].create(po_line_vals)

                # The ORM will automatically:
                # - Calculate price_subtotal, price_total, price_tax
                # - Set proper currency_id from the parent PO
                # - Set partner_id from the parent PO
                # - Handle all constraints properly
                # - Set create/write dates and user IDs
                # - Apply taxes based on product configuration

                print(f"Created PO line: {po_line.id} for product: {product.name} and category: {product.vehicle_category_id.name}")
                if is_tp_truck_product:
                    break

        purchase_order.fleet_do_id = self.id
        self.purchase_order_id = po_id

    # Alternative method with even more automation
    def _create_po_lines_orm_advanced(self, po_id):
        """Advanced version that leverages more ORM features"""

        purchase_order = self.env['purchase.order'].browse(po_id)

        # Prepare all PO line values at once
        po_line_vals_list = []

        for line in self.po_line_ids:
            if line.product_id:
                # Get the best price for this product from this vendor
                price_unit = 0.0

                # Check supplier info first
                supplier_info = line.product_id._select_seller(
                    partner_id=purchase_order.partner_id,
                    quantity=line.product_uom_qty,
                    date=purchase_order.date_order,
                    uom_id=line.product_uom
                )

                if supplier_info:
                    price_unit = supplier_info.price
                else:
                    # Fallback to product cost
                    price_unit = line.product_id.standard_price or 0.0

                po_line_vals = {
                    'order_id': po_id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': price_unit,
                    'name': line.name or line.product_id.name,
                    'sequence': line.sequence,
                    'date_planned': fields.Datetime.now(),
                }

                po_line_vals_list.append(po_line_vals)

        # Create all PO lines in batch
        if po_line_vals_list:
            po_lines = self.env['purchase.order.line'].create(po_line_vals_list)

            # Optionally trigger recomputation of PO totals
            purchase_order._amount_all()

            return po_lines

    # Even simpler approach using Odoo's built-in methods
    def _create_po_lines_orm_simple(self, po_id):
        """Simplest approach using Odoo's standard methods"""

        purchase_order = self.env['purchase.order'].browse(po_id)

        for line in self.po_line_ids:
            if line.product_id:
                # Use the standard PO line creation method
                po_line = self.env['purchase.order.line'].new({
                    'order_id': po_id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                })

                # Trigger onchange to populate all fields automatically
                po_line._onchange_product_id()
                po_line._onchange_quantity()

                # Override with custom values if needed
                if line.name:
                    po_line.name = line.name
                po_line.sequence = line.sequence

                # Create the record
                po_line = po_line._convert_to_write(po_line._cache)
                self.env['purchase.order.line'].create(po_line)

    @api.constrains('po_line_ids', 'po_line_ids.is_header')
    def _check_max_one_header(self):
        is_from_revision_wizard = self.env.context.get('is_from_revision_wizard')

        for rec in self:
            headers = rec.po_line_ids.filtered('is_header')
            if len(headers) > 1 and not is_from_revision_wizard:
                raise ValidationError(_("Hanya boleh satu Header pada DO '%s'.") % (rec.display_name,))
            
    def _is_comment_required_for_current_tier(self):
        self.ensure_one()
        tdef = self._tier_def_for_state(self.state)
        if not tdef:
            return False
        # beberapa instalasi beda nama field; cek yang umum
        for fname in ('has_comment', 'require_comment', 'need_comment'):
            if fname in tdef._fields and getattr(tdef, fname):
                return True
        return False
    
    def _open_reject_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.do.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Alasan Penolakan'),
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
            }
        }

    def _label_for_state(self, review_state):
        return {
            'approved_operation_spv': _('Operation Supervisor'),
            'approved_cashier': _('Cashier'),
            'approved_adh': _('Administration Head'),
            'approved_by_kacab': _('Kepala Cabang'),
        }.get(review_state, review_state)
        
    def _tier_def_for_state(self, state):
        review_state = _REVIEW_TARGET_BY_STATE.get(state)
        if not review_state:
            return False
        TierDef = self.env['tier.definition']
        domain = [('review_state', '=', review_state)]
        if 'model_id' in TierDef._fields:
            domain.append(('model_id.model', '=', self._name))
        else:
            domain.append(('model', '=', self._name))
        return TierDef.search(domain, limit=1)
    
    def _close_all_todo_safe(self):
        todo = self.env.ref('mail.mail_activity_data_todo')
        acts = self.activity_ids.filtered(lambda a: a.activity_type_id.id == todo.id and not a.date_done)
        for act in acts:
            act.action_feedback(feedback=_("Rejected by %s") % self.env.user.name)

    def _parse_api_dt(self, s):
        if not s:
            return False
        if isinstance(s, str) and s.startswith('0001-01-01'):
            return False
        try:
            return fields.Datetime.to_datetime(s)
        except Exception:
            return False

    @api.depends('status_do')
    def _compute_is_already_do_match(self):
        for rec in self:
            if rec.status_do:
                if rec.status_do == 'DO Match':
                    rec.is_already_do_match = True
                else:
                    rec.is_already_do_match = False

    @api.depends('status_do')
    def _compute_is_already_do_unmatch(self):
        for rec in self:
            if rec.status_do:
                if rec.status_do == 'DO Unmatch':
                    rec.is_already_do_unmatch = True
                else:
                    rec.is_already_do_unmatch = False
    
    def _upsert_report_from_api(self, payload):
        _logger.info(f"=== DO REPORT ===> Response: {payload}")
        """payload = dict hasil response.json() dari API EasyGO (yang berisi key 'Data')."""
        Report = self.env['fleet.do.report'].sudo()

        data_list = []
        if isinstance(payload, dict):
            data_list = payload.get('Data') or []
        if not isinstance(data_list, list):
            data_list = []
        _logger.info(f"=== DO DATA ===> Response: {data_list}")
        for entry in data_list:
            # Ambil nilai header DO
            no_do       = entry.get('no_do') or ''
            plat_nomor  = entry.get('nopol') or ''
            status_code = entry.get('status_do')  # bisa int/str
            try:
                status_code = int(status_code) if status_code is not None else None
            except Exception:
                status_code = None

            external_do_id = entry.get('do_id')
            # Cari DO Odoo berdasarkan name == no_do
            fleet_do = self.env['fleet.do'].search([('name', '=', no_do)], limit=1)

            # Dua lokasi: asal & tujuan
            for loc in ('asal', 'tujuan'):
                items = entry.get(loc) or []
                for it in items:
                    # Ambil nama geofence
                    geo_name = it.get('geo_label') or it.get('geo_nm') or ''
                    masuk    = self._parse_api_dt(it.get('tgl_masuk'))
                    keluar   = self._parse_api_dt(it.get('tgl_keluar'))

                    vals = {
                        'fleet_do_id': fleet_do.id or False,
                        'external_do_id': str(external_do_id) if external_do_id else False,
                        'no_do': no_do,
                        'plat_nomor': plat_nomor,
                        'status_do': status_code if status_code is not None else 0,
                        'location': loc,
                        'geo_name': geo_name,
                        'tgl_masuk': masuk,
                        'tgl_keluar': keluar,
                        # (opsional) status_desc dari ket_status_do bila ada
                        'status_desc': entry.get('ket_status_do') or False,
                    }

                    # Upsert sesuai rule: (no_do, status_do, location)
                    rec = Report.search([
                        ('no_do', '=', no_do),
                        ('status_do', '=', vals['status_do']),
                        ('location', '=', loc),
                    ], limit=1)

                    if rec:
                        rec.write(vals)
                    else:
                        Report.create(vals)

    @api.model
    def cron_sync_do_report(self):
        """
        Cron: ambil semua DO yang punya do_id, lalu hit API dan upsert ke fleet.do.report.
        Batch size & days_back bisa diatur via ir.config_parameter:
          - easygo.cron_batch_size (default 50)
          - easygo.cron_days_back  (default 30)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        batch_size = int(ICP.get_param('easygo.cron_batch_size', '50'))
        days_back  = int(ICP.get_param('easygo.cron_days_back',  '30'))

        since_dt = fields.Datetime.now() - relativedelta(days=days_back)

        domain = [
            ('do_id', '!=', False),
        ]

        dos = self.sudo().search(domain, limit=batch_size, order='write_date desc')
        _logger.info("cron_sync_do_report: processing %s DO(s)", len(dos))

        for do in dos:
            try:
                # Panggil flow yang sudah kamu buat (hit API + update vehicle + upsert report)
                do.sudo().action_update_status_do(do)
            except Exception as e:
                _logger.exception("cron_sync_do_report: DO %s (%s) failed: %s", do.id, do.name, e)
                
        return True
    
    def sync_do_report_for_range(self, date_start, date_end, fleet_do_id):
        """Dipanggil wizard: hit API utk semua DO yg punya do_id, pada rentang tanggal."""
        # susun start/stop string
        if date_start > date_end:
            date_start, date_end = date_end, date_start
        start_str = datetime.combine(date_start, time(0,0,0)).strftime('%Y-%m-%d %H:%M:%S')
        stop_str  = datetime.combine(date_end,   time(23,59,59)).strftime('%Y-%m-%d %H:%M:%S')

        domain = [('do_id', '!=', False), ('id', '=', fleet_do_id)]
        dos = self.sudo().search(domain, order='write_date desc')
        _logger.info("sync_do_report_for_range: %s DO(s), %s -> %s", len(dos), start_str, stop_str)
        for do in dos:
            try:
                do.sudo().action_update_status_do(do, start_str=start_str, stop_str=stop_str, fleet_do_id=fleet_do_id)
            except Exception as e:
                _logger.exception("sync_do_report_for_range failed for %s (%s): %s", do.id, do.name, e)
        return True


class FleetDOLog(models.Model):
    _name = 'fleet.do.log'

    do_id = fields.Many2one('fleet.do')
    prev_driver_id = fields.Many2one('res.partner')
    driver_id = fields.Many2one('res.partner')
    prev_rekening_number = fields.Char()
    prev_rekening_name = fields.Char()
    prev_rekening_bank = fields.Char()
    rekening_number = fields.Char()
    rekening_name = fields.Char()
    rekening_bank = fields.Char()

class FleetDoLine(models.Model):
    _name = 'fleet.do.line'
    _rec_name = 'fleet_do_id'

    fleet_do_id = fields.Many2one('fleet.do')
    license_plat = fields.Char()
    attachment_ids = fields.Many2many(comodel_name='ir.attachment')
    no_surat_jalan = fields.Char()
    status = fields.Selection([('outstanding', 'On Delivery'), ('done', 'Done')], default='outstanding',
                              compute='compute_status', store=True)
    bop_type = fields.Char('BOP Type')
    bank_name = fields.Many2one('res.partner.bank')

    @api.depends('no_surat_jalan')
    def compute_status(self):
        for rec in self:
            rec.status = 'outstanding'
            if rec.no_surat_jalan:
                rec.status = 'done'

    def action_open_budget_entries(self):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_journal_line')
        action['domain'] = [('id', 'in', self.fleet_do_id.journal_entry_ids.ids)]
        return action
class FleetDoOption(models.Model):
    _name = 'fleet.do.option'
    _rec_name = 'fleet_do_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    order_id = fields.Many2one('sale.order')
    fleet_do_id = fields.Many2one('fleet.do')
    product_code = fields.Char('PRODUCT CODE')
    ce_code = fields.Char('CE. CODE')
    product_id = fields.Many2one('product.product', 'PRODUCT NAME')
    product_description = fields.Text('DESCRIPTION')
    qty = fields.Integer('QUANTITY')
    uom_id = fields.Many2one('uom.uom', 'UoM')
    currency_id = fields.Many2one('res.currency', related='fleet_do_id.currency_id')
    unit_price = fields.Monetary('UNIT PRICE', currency_field='currency_id')
    # ce_code = fields.Many2one(
    #     'create.contract.line',
    #     string='CE. CODE',
    # )


class BopLine(models.Model):
    _name = 'bop.line'
    _rec_name = 'bop_no'
    _description = 'BOP list'
    _inherit = ['tier.validation','mail.thread', 'mail.activity.mixin', 'portfolio.view.mixin']
    _tier_validation_manual_config = True

    fleet_do_id = fields.Many2one(
        'fleet.do',
        domain="[('state', 'in', ('approved_operation_spv', 'approved_cashier', 'approved_adh', 'approved_by_kacab', 'done'))]",
        readonly=True,
        index=True, required=True, ondelete='cascade'
    )
    date = fields.Date('Date', default=fields.Date.today())
    bop_no = fields.Char('BOP NO.')
    bop_value = fields.Monetary('BOP Value', related='fleet_do_id.nominal', currency_field='currency_id')
    bop_percentage_paid = fields.Float('BOP Percentage Paid', related='fleet_do_id.bop_percentage_paid', store=True)
    currency_id = fields.Many2one('res.currency', related='fleet_do_id.currency_id')
    driver_id = fields.Many2one('res.partner', related='fleet_do_id.driver_id', store=True)
    origin_id = fields.Many2one('master.origin', 'Origin', related='fleet_do_id.origin_id', store=True)
    destination_id = fields.Many2one('master.destination', 'Destination',
                                     related='fleet_do_id.destination_id', store=True)
    bop_state = fields.Selection([
        ('partial', 'Partial Payment'),
        ('full', 'Full Payment'),
    ], compute='_compute_bop_state', store=True, tracking=True)
    amount_paid = fields.Monetary('Amount Paid', currency_field='currency_id', store=True)
    is_exported_to_mcm = fields.Boolean('Exported to MCM', readonly=True)
    paid_status = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('paid', 'Paid')
    ], 'Paid Status', readonly=True, store=True)
    is_sent_to_oracle = fields.Boolean('Sent to Oracle', readonly=True)
    state = fields.Selection([
        ('draft', 'To Approve'),
        ('approved_cashier', 'Approved by Cashier'),
        ('approved_adh', 'Approved by Administration Head'),
        ('approved_by_kacab', 'Approved by Kepala Cabang'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    nominal = fields.Monetary(string="Nominal", related='fleet_do_id.nominal', readonly=True)
    prev_nominal = fields.Monetary(string="Nominal", related='fleet_do_id.prev_nominal', readonly=True)
    bop_driver_used = fields.Float(string="BOP Driver yang digunakan", related='fleet_do_id.bop_driver_used', readonly=True)
    bop_paid = fields.Monetary(related='fleet_do_id.bop_paid', readonly=True)
    bop_unpaid = fields.Monetary(related='fleet_do_id.bop_unpaid', readonly=True)
    no_lambung = fields.Char(string="No. Lambung", related='fleet_do_id.no_lambung', readonly=True)
    transfer_to = fields.Many2one(string="Transfer To", related='fleet_do_id.transfer_to', readonly=True)
    bank_cash = fields.Many2one(string="Bank / Cash", related='fleet_do_id.bank_cash', readonly=True)
    rekening_number = fields.Char(string="No. Rekening", related='fleet_do_id.rekening_number', readonly=True)
    rekening_name = fields.Char(string="Nama Rekening", related='fleet_do_id.rekening_name', readonly=True)
    rekening_bank = fields.Char('Nama Bank', related='fleet_do_id.rekening_bank', readonly=True)
    bank_name = fields.Many2one(string="Bank Name", related='fleet_do_id.bank_name', readonly=True)
    bop_ids = fields.One2many(related='fleet_do_id.bop_ids')
    approval_date_cashier = fields.Date('Approval Date', store=True)
    approval_date_by_kacab = fields.Date('Approval Date', store=True)
    approval_by_cashier = fields.Many2one('res.users', 'Approval By', store=True)
    approval_by_kacab = fields.Many2one('res.users', 'Approval By', store=True)
    bop_percentage_paid_form = fields.Float('BOP Percentage Paid', compute='compute_bop_line_form', store=True)
    review_ids = fields.One2many(
        comodel_name="tier.review",
        inverse_name="res_id",
        compute='_compute_review_ids_filtered',
        string="Riwayat Persetujuan BOP",
    )
    reject_by = fields.Many2one('res.users', 'Reject By', store=True)
    is_created_vendor_bill = fields.Boolean(string="Created Vendor Bill", default=False)
    state_do = fields.Selection(
        related='fleet_do_id.state',
        store=True,
        readonly=True,
        string='State DO'
    )
    filtered_bop_ids = fields.One2many(
        'bop.line',
        compute='_compute_filtered_bop_ids',
        string='Filtered BOP IDs',
    )
    fleet_do_state = fields.Selection(related='fleet_do_id.state', store=True)
    percentage_paid = fields.Float('Percentage Paid', store=True)
    is_created_form = fields.Char(string='Created BOP FROM')
    has_access_state = fields.Boolean(default=False, compute='_compute_has_access_state')
    sibling_bop_ids = fields.One2many(
        'bop.line',
        compute='_compute_sibling_bop_ids',
        inverse='_inverse_sibling_bop_ids',
        string='Daftar BOP pada DO yang sama'
    )
    review_do_ids = fields.One2many(
        string="Riwayat Persetujuan DO",
        related='fleet_do_id.review_ids'
    )
    bop_additional_cost_ids = fields.One2many(
        'bop.line',
        compute='_compute_bop_additional_cost_ids',
        string='Daftar Biaya Tambahan BOP'
    )
    has_access_state_do = fields.Boolean(default=False, compute='_compute_has_access_state_do')
    is_settlement = fields.Boolean(default=False, store=True, index=True)
    just_created = fields.Boolean(default=False, copy=False, index=True)
    asset_type = fields.Selection(
        related='fleet_do_id.vehicle_id.asset_type',
        store=True, readonly=True
    )
    vendor_bill_id = fields.Many2one(
        'account.move', string='Vendor Bill', index=True, ondelete='set null',
        domain=[('move_type', '=', 'in_invoice')]
    )
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', index=True, ondelete='set null',
        domain=[('move_type', '=', 'out_invoice')]
    )
    current_reviewer_id = fields.Many2one('res.users', string='Current Reviewer', index=True)
    no_surat_jalan = fields.Char(readonly=True)
    is_additional_cost = fields.Boolean(default=False, store=True, index=True)
    has_additional_cost = fields.Boolean(default=False, compute='_compute_has_additional_cost')
    product_ids = fields.Many2many(
        'product.product',
        'bop_line_product_rel',
        'bop_line_id', 'product_id',
        string='Produk Biaya Tambahan'
    )
    attachment = fields.Binary(string='Lampiran', attachment=True)
    attachment_filename = fields.Char(string='Nama File')
    
    def _compute_has_additional_cost(self):
        self.ensure_one()
        if not self.fleet_do_id:
            raise UserError(_("Pilih DO dulu."))
        
        do = self.fleet_do_id
        bop_additional_cost = do.bop_ids.filtered(lambda x: x.is_additional_cost)
        if bop_additional_cost:
            self.has_additional_cost = True
            
        print(self.has_additional_cost)


    def _tier_def(self, review_state):
        TierDef = self.env['tier.definition']
        domain = [('review_state', '=', review_state)]
        if 'model_id' in TierDef._fields:
            domain.append(('model_id.model', '=', self._name))
        else:
            domain.append(('model', '=', self._name))
        return TierDef.search(domain, limit=1)

    def _close_my_todo_activity(self):
        todo = self.env.ref('mail.mail_activity_data_todo')
        acts = self.activity_ids.filtered(
            lambda a: a.activity_type_id.id == todo.id and a.user_id.id == self.env.user.id and not a.date_done
        )
        for act in acts:
            act.action_feedback(feedback=_("Approved by %s") % self.env.user.name)

    def _schedule_todo_for(self, user, summary, note):
        todo = self.env.ref('mail.mail_activity_data_todo')
        Activity = self.env['mail.activity'].sudo()
        exists = Activity.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', todo.id),
            ('user_id', '=', user.id),
            ('date_done', '=', False),
        ], limit=1)
        if not exists:
            # self.message_subscribe(partner_ids=[user.partner_id.id])
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=summary,
                note=note,
                date_deadline=fields.Date.today(),
            )

    def _compute_has_access_state_do(self):
        for rec in self:

            state = ''
            if self.fleet_do_id.state == 'to_approve':
                state = 'approved_operation_spv'
            elif self.fleet_do_id.state == 'approved_operation_spv':
                state = 'approved_cashier'
            elif self.fleet_do_id.state == 'approved_cashier':
                state = 'approved_adh'
            elif self.fleet_do_id.state == 'approved_adh':
                state = 'approved_by_kacab'

            tier_definition = self.env['tier.definition'].search([
                ('review_state', '=', state),
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', 'fleet.do')
            ], limit=1)

            rec.has_access_state_do = bool(tier_definition)

    @api.depends('fleet_do_id')
    def _compute_sibling_bop_ids(self):
        for rec in self:
            if rec.fleet_do_id:
                rec.sibling_bop_ids = self.env['bop.line'].search([
                    ('fleet_do_id', '=', rec.fleet_do_id.id),
                    ('is_additional_cost', '=', False),
                ])
            else:
                rec.sibling_bop_ids = False
                
    @api.depends('fleet_do_id')
    def _compute_bop_additional_cost_ids(self):
        for rec in self:
            if rec.fleet_do_id:
                rec.bop_additional_cost_ids = self.env['bop.line'].search([
                    ('fleet_do_id', '=', rec.fleet_do_id.id),
                    ('is_additional_cost', '=', True),
                ])
            else:
                rec.bop_additional_cost_ids = False

    def _inverse_sibling_bop_ids(self):
        bop = self.env['bop.line'].with_context(prefetch_fields=False)
        for rec in self:
            do_id = (
                rec.fleet_do_id.id
                or rec._origin.fleet_do_id.id
                or self.env.context.get('default_fleet_do_id')
                or self.env.context.get('active_id')
            )
            if not do_id:
                raise UserError("Tidak bisa menyimpan karena Fleet DO belum dipilih.")

            existing = bop.search([
                ('fleet_do_id', '=', do_id),
                ('is_additional_cost', '=', False),
            ])
            
            desired = rec.sibling_bop_ids

            # CREATE untuk baris 'phantom' (NewId)
            for nl in desired.filtered(lambda l: not l.id):
                vals = {
                    'fleet_do_id': do_id,
                    'percentage_paid': getattr(nl, 'percentage_paid', 0.0) or 0.0,
                }
                vals = rec._prepare_bop_create_vals(vals)
                bop.create(vals)

            # =========================
            # Sinkron remove / attach
            # =========================
            desired_real = desired.filtered('id')
            to_remove = (existing - desired_real)

            # BLOKIR remove jika state tertentu
            locked = to_remove.filtered(lambda r: r.state == 'approved_by_kacab')
            
            if locked:
                raise UserError(
                    "Tidak boleh menghapus/melepas BOP yang sudah disetujui Kepala Cabang:\n- "
                    + "\n- ".join(locked.mapped(lambda r: r.bop_no or f"ID {r.id}"))
                )

            # Aman: putuskan relasi untuk sisanya
            to_remove.write({'fleet_do_id': False})

            # Attach: baris yang diinginkan tapi belum menunjuk ke DO ini → pindahkan
        desired_real.filtered(lambda r: r.fleet_do_id.id != do_id).write({'fleet_do_id': do_id})

    def _prepare_bop_create_vals(self, vals):
        """Lengkapi vals untuk create bop.line baru berdasarkan DO."""
        do_id = vals.get('fleet_do_id')
        do = self.env['fleet.do'].browse(do_id)
        if not do:
            return vals

        # Ambil label selection branch_project dengan aman
        bp_codes = do.po_line_ids.order_id.mapped('branch_project')
        code = bp_codes[0] if bp_codes else False
        selection = dict(self.env['sale.order']._fields['branch_project'].selection)
        bp_label = selection.get(code, code)

        bop_no = self.generate_fleet_bop_name(bp_label)
        
        longest_line = max(do.po_line_ids, key=lambda l: (l.distance or 0), default=None)
        nominal = (vals.get('percentage_paid', 0.0) / 100.0) * (do.nominal or 0.0)
        
        if do.bop_state == 'partial' and len(do.bop_ids) > 1:
            nominal = float_round(nominal, precision_digits=0, rounding_method='DOWN')
        else:
            nominal = float_round(nominal, precision_digits=0, rounding_method='UP')
        
        # self._check_bop_not_exceed_nominal(do, nominal)
        self._validate_bop_nominal(do, nominal)

        vals.update({
            'date': fields.Date.today(),
            'currency_id': self.env.user.company_id.currency_id.id,
            'driver_id': do.driver_id.id if do.driver_id else False,
            'origin_id': longest_line.origin_id.id if longest_line else False,
            'destination_id': longest_line.destination_id.id if longest_line else False,
            'paid_status': 'not_paid',
            'is_sent_to_oracle': False,
            'amount_paid': nominal,
            'bop_no': bop_no,
        })

        # kalau ini harus akumulasi, jangan overwrite:
        do.write({'bop_paid': (do.bop_paid or 0.0) + nominal})
        return vals

    def action_save_and_open_last_bop(self):
        self.ensure_one()
        if not self.fleet_do_id:
            raise UserError(_("Pilih DO dulu."))

        # cari baris yang baru dibuat via tombol ini
        last = self.env['bop.line'].search([
            ('fleet_do_id', '=', self.fleet_do_id.id),
            ('just_created', '=', True),
            ('is_additional_cost', '=', False),
        ], order='id desc', limit=1)
        print(last)
        if not last:
            # fallback ke yang paling baru oleh user ini, kalau perlu
            last = self.env['bop.line'].search([
                ('fleet_do_id', '=', self.fleet_do_id.id),
                ('create_uid', '=', self.env.user.id),
                ('is_additional_cost', '=', False),
            ], order='create_date desc', limit=1)

        if not last:
            raise UserError("Tidak ada baris BOP baru yang ditambahkan.")

        # reset flag biar gak “nempel”
        last.just_created = False

        wiz = self.env['bop.save.success.wizard'].create({
            'bop_id': last.id,
            'message': _("BOP berhasil dibuat. Silakan lanjutkan ke proses submit."),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bop.save.success.wizard',
            'name': _('BOP Berhasil Dibuat'),
            'view_mode': 'form',
            'res_id': wiz.id,
            'target': 'new',
        }


    @api.onchange('percentage_paid', 'fleet_do_id')
    def _onchange_percentage_paid(self):
        for rec in self:
            do = rec.fleet_do_id
            if not do or rec.percentage_paid is None:
                continue
            
            proposed = rec._calc_nominal_from_percent(do, rec.percentage_paid)
            rec.amount_paid = proposed
    
    @api.depends('percentage_paid')
    def _compute_bop_state(self):
        for rec in self:
            do = rec.fleet_do_id
            if len(do.bop_ids) == 1:
                pct = rec.percentage_paid or 0.0
                if pct >= 100.0:
                    rec.bop_state = 'full'
                    rec.fleet_do_id.bop_state = 'full'
                elif pct > 0.0:
                    rec.bop_state = 'partial'
                    rec.fleet_do_id.bop_state = 'partial'
                else:
                    rec.bop_state = False
                    rec.fleet_do_id.bop_state = False

    @api.depends('fleet_do_id.bop_ids.bop_no')
    def _compute_filtered_bop_ids(self):
        for rec in self:
            bop_lines = rec.fleet_do_id.bop_ids.filtered(lambda x: x.bop_no and x.bop_no.strip())
            rec.filtered_bop_ids = bop_lines

    def generate_fleet_bop_name(self, code):
        sequence_code = 'bop.line'+'.'+code
        nomor_urut = self.env['ir.sequence'].next_by_code(sequence_code) or '00000'
        bulan = datetime.today().month
        tahun = datetime.today().year
        kode = code if code else 'LMKS'
        return f'BOP/{nomor_urut}/{kode}/{bulan}/{tahun}'

    def _compute_has_access_state(self):
        for rec in self:
            state = ''
            if self.state == 'draft':
                state = 'approved_cashier'
            elif self.state == 'approved_cashier':
                state = 'approved_adh'
            elif self.state == 'approved_adh':
                state = 'approved_by_kacab'

            tier_definition = self.env['tier.definition'].search([
                ('review_state', '=', state),
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', self._name)
            ], limit=1)
            
            rec.has_access_state = bool(tier_definition)
            
    # --- Helper untuk validasi kuota ---
    def _max_bop_rows_for_do(self, do):
        if do.bop_state == 'full':
            return 1
        if do.bop_state == 'partial':
            return 2
        return None  # tak dibatasi; ganti ke 2 kalau mau default 2

    def _check_do_row_limit(self, do, additional_count=1):
        if do.bop_state == 'partial' and (do.state or '').lower() != 'done':
            raise UserError(_("DO %s belum 'Done'. Tidak bisa membuat BOP baru")
                            % do.display_name)

        max_allowed = self._max_bop_rows_for_do(do)
        if not max_allowed:
            return  # tidak dibatasi

        # Kunci baris2 BOP DO ini agar aman dari race sederhana
        self.env.cr.execute("SELECT id FROM bop_line WHERE fleet_do_id = %s FOR UPDATE", [do.id])

        existing = self.env['bop.line'].with_context(prefetch_fields=False).search_count([
            ('fleet_do_id', '=', do.id),
            ('is_additional_cost', '=', False)
        ])

        if existing + additional_count > max_allowed:
            if do.bop_state == 'full':
                msg = _("BOP untuk DO %s hanya boleh 1 baris (Status BOP = Full Payment).") % do.display_name
            else:
                msg = _("BOP untuk DO %s maksimal 2 baris (Status BOP = Partial Payment).") % do.display_name
            raise UserError(msg)


    @api.model_create_multi
    def create(self, vals_list):
        default_do = self.env.context.get('default_fleet_do_id')
        FleetDo = self.env['fleet.do']

        # --- Hitung rencana penambahan per DO (untuk create_multi) ---
        planned = {}  # {do_id: count_new_rows}
        for vals in vals_list:
            if vals.get('is_created_form') == 'SO':
                continue
            
            if vals.get('is_created_form') == 'BOP':
                continue
            
            do_id = vals.get('fleet_do_id') or default_do
            if do_id:
                vals['fleet_do_id'] = do_id
                planned[do_id] = planned.get(do_id, 0) + 1

        # --- Validasi kuota sebelum create ---
        for do_id, add_count in planned.items():
            do = FleetDo.browse(do_id)
            self._check_do_row_limit(do, additional_count=add_count)

        # --- Set flag settlement & siapkan turunan ---
        for vals in vals_list:
            if vals.get('is_created_form') == 'SO':
                continue

            do_id = vals.get('fleet_do_id') or default_do
            if do_id:
                do = FleetDo.browse(do_id)
                vals['fleet_do_id'] = do_id
                vals['is_settlement'] = (do.state == 'done')

            if vals.get('percentage_paid') and vals.get('fleet_do_id'):
                self._inject_bop_fields(vals)
                
            # flag baris baru bila tombol memintanya
            if self.env.context.get('mark_recent'):
                vals['just_created'] = True

        # --- Lanjut create ---
        recs = super().create(vals_list)
        return recs
    
    def write(self, vals):
        # --- Cek kuota kalau DO tidak berubah ---
        # if 'fleet_do_id' in vals and vals['fleet_do_id']:
        #     # Kalau DO dipindahkan
        #     new_do = self.env['fleet.do'].browse(vals['fleet_do_id'])
        #     self._check_do_row_limit(new_do, additional_count=len(self))
        # else:
        #     # Kalau fleet_do_id tetap sama, tapi ini create baris baru? tidak relevan di write
        #     # Kalau mau batasi edit, bisa cek DO yang sama
        #     for rec in self:
        #         if rec.fleet_do_id:
        #             self._check_do_row_limit(rec.fleet_do_id, additional_count=0)

        # --- Lanjut logika percentage_paid ---
        if vals.get('percentage_paid'):
            for rec in self:
                if rec.state in ['approved_by_kacab', 'approved_adh', 'done']:
                    raise UserError(_("Data dengan status '%s' tidak bisa diedit.") % rec.state)
            
                update_vals = rec._get_vals_from_percentage_paid(vals['percentage_paid'])
                super(BopLine, rec).write(update_vals)
            return True

        return super().write(vals)
    def _inject_bop_fields(self, vals):
        # pastikan DO ada
        do = self.env['fleet.do'].browse(vals['fleet_do_id'])
        if not do:
            return vals

        selection = dict(self.env['sale.order']._fields['branch_project'].selection)
        bp_codes = do.po_line_ids.order_id.mapped('branch_project') or []
        bp_label = selection.get(bp_codes[0], bp_codes[0] if bp_codes else False)
        bop_no = self.generate_fleet_bop_name(bp_label)

        longest_line = max(do.po_line_ids, key=lambda l: (l.distance or 0), default=None)

        max_pct = self._remaining_percentage(do, exclude_line=None)  # record belum ada id
        pct = vals.get('percentage_paid', 0.0) or 0.0
        if pct > max_pct:
            pct = max_pct
            vals['percentage_paid'] = pct
            
        nominal = self._calc_nominal_from_percent(do, pct)
        unpaid, new_total_paid, nominal = self._validate_bop_nominal(do, nominal, cap_to_unpaid=True)
        
        do.write({'bop_paid': new_total_paid})

        vals.update({
            'date': fields.Date.today(),
            'currency_id': (do.currency_id or self.env.company.currency_id).id,
            'driver_id': do.driver_id.id if do.driver_id else False,
            'origin_id': longest_line.origin_id.id if longest_line else False,
            'destination_id': longest_line.destination_id.id if longest_line else False,
            'paid_status': 'not_paid',
            'is_sent_to_oracle': False,
            'amount_paid': nominal,   # <-- nominal baris create
            'bop_no': bop_no,
        })

        return vals

    def _get_vals_from_percentage_paid(self, percentage_paid):
        self.ensure_one()
        do = self.fleet_do_id

        selection = dict(self.env['sale.order']._fields['branch_project'].selection)
        bp_codes = do.po_line_ids.order_id.mapped('branch_project') or []
        bp_value = selection.get(bp_codes[0]) if bp_codes else False
        bop_no = self.generate_fleet_bop_name(bp_value)

        longest_dist = max(do.po_line_ids.mapped('distance') or [0])
        longest_lines = do.po_line_ids.filtered(lambda l: (l.distance or 0) == longest_dist)
        origin_id = longest_lines[:1].origin_id.id if longest_lines else False
        destination_id = longest_lines[:1].destination_id.id if longest_lines else False

        # hitung nominal & validasi
        # --- Batasi persentase dulu ---
        max_pct = self._remaining_percentage(do, exclude_line=self)
        pct = percentage_paid or 0.0
        if pct > max_pct:
            pct = max_pct
            # atau: raise ValidationError(_("Persentase baris ini maksimal %.2f%%.") % max_pct)
        nominal = self._calc_nominal_from_percent(do, pct)
        unpaid, new_total_paid, nominal = self._validate_bop_nominal(do, nominal, cap_to_unpaid=True)


        do.write({'bop_paid': new_total_paid})

        return {
            'percentage_paid': pct,
            'date': fields.Date.today(),
            'currency_id': (do.currency_id or self.env.company.currency_id).id,
            'driver_id': do.driver_id.id if do.driver_id else False,
            'origin_id': origin_id,
            'destination_id': destination_id,
            'paid_status': 'not_paid',
            'is_sent_to_oracle': False,
            'fleet_do_id': do.id,
            'amount_paid': nominal,   # <-- nominal baris ini, bukan total
            'bop_no': bop_no,
        }

    def _rounding_for_this_line(self, do):
        """UP bila ini baris pertama; selain itu DOWN.
        - Create baris 1 (belum ada line) -> UP
        - Create baris 2+ (sudah ada minimal 1 line) -> DOWN
        - Edit baris pertama -> tetap UP meski ada baris lain
        - Edit baris kedua+ -> DOWN
        """
        if not self.id:
            # record baru (belum disave)
            return 'UP' if len(do.bop_ids) == 0 else 'DOWN'
        # record tersimpan: cek apakah dia baris pertama (berdasarkan id terkecil)
        saved_lines = do.bop_ids.filtered(lambda l: l.id)
        if not saved_lines:
            return 'UP'
        first = saved_lines.sorted(lambda l: l.id)[0]
        return 'UP' if first.id == self.id else 'DOWN'

    def _calc_nominal_from_percent(self, do, percentage_paid):
        base = (percentage_paid / 100.0) * (do.nominal or 0.0)
        rounding = self._rounding_for_this_line(do)
        return float_round(base, precision_digits=0, rounding_method=rounding)
    
    def _remaining_percentage(self, do, exclude_line=None):
        # total persen terpakai dari baris lain
        # others = do.bop_ids.filtered(lambda l: not exclude_line and l.is_additional_cost is False or l.id != exclude_line.id)
        others = do.bop_ids.filtered(
            lambda l: (not l.is_additional_cost) and (not exclude_line or l.id != exclude_line.id)
        )
        used = sum(others.mapped('percentage_paid') or [0.0])

        if (do.bop_state or '').lower() == 'full':
            # mode full: hanya satu baris diizinkan, maksimal 100%
            return 100.0 if float_is_zero(used, precision_rounding=0.0001) else 0.0

        rem = 100.0 - (used or 0.0)
        return max(0.0, rem)
    
    @api.constrains('percentage_paid', 'fleet_do_id')
    def _constrains_percentage_remaining(self):
        for rec in self:
            if not rec.fleet_do_id:
                continue
            max_pct = rec._remaining_percentage(rec.fleet_do_id, exclude_line=rec)
            if rec.percentage_paid is None:
                continue
            if rec.percentage_paid < 0.0:
                raise ValidationError(_("Persentase tidak boleh negatif."))
            if rec.percentage_paid > max_pct:
                raise ValidationError(
                    _("Persentase baris ini maksimal %.2f%% (sisa dari 100%%).") % (max_pct,)
                )
        
    def _validate_bop_nominal(self, do, nominal, cap_to_unpaid=True):
        cur = do.currency_id or self.env.user.company_id.currency_id
        # paid_except_self = sum(do.bop_ids.filtered(lambda l: l.id != self.id and l.is_additional_cost is False).mapped('amount_paid'))
        paid_except_self = sum(
            do.bop_ids
            .filtered(lambda l: l.id != self.id and (not l.is_additional_cost))
            .mapped('amount_paid')
        )
        do_nominal_up = float_round(do.nominal or 0.0, precision_digits=0, rounding_method='UP')
        unpaid = do_nominal_up - float_round(paid_except_self, precision_digits=0, rounding_method='DOWN')

        if float_is_zero(unpaid, precision_rounding=cur.rounding) or float_compare(unpaid, 0.0, precision_rounding=cur.rounding) <= 0:
            raise ValidationError(_("BOP untuk DO ini sudah 100%. Tidak bisa menambah pembayaran lagi."))

        if float_is_zero(nominal, precision_rounding=cur.rounding):
            raise ValidationError(_("Nominal hasil persen membulat ke 0. Perbesar persen atau pakai mode nominal."))

        # Jika nominal lewat sedikit, batasi ke unpaidBiaya Tambahan
        if float_compare(nominal, unpaid, precision_rounding=cur.rounding) == 1:
            if cap_to_unpaid:
                nominal = unpaid
            else:
                raise ValidationError(_("Nominal melebihi sisa tagihan. Periksa kembali persentasenya."))

        new_total_paid = float_round(paid_except_self + nominal, precision_digits=0, rounding_method='DOWN')
        if float_compare(new_total_paid, do_nominal_up, precision_rounding=cur.rounding) == 1:
            # Harusnya tak terjadi bila di-cap di atas
            if cap_to_unpaid:
                nominal = do_nominal_up - paid_except_self
                new_total_paid = do_nominal_up
            else:
                raise ValidationError(_("Total BOP terbayar melebihi nominal DO."))

        return unpaid, new_total_paid, nominal

    def _check_bop_not_exceed_nominal(self, do, additional_paid):
        # Hitung jumlah BOP yang sudah ada untuk DO ini
        total_bop_count = self.env['bop.line'].search_count([
            ('fleet_do_id', '=', do.id)
        ])
        
        do_nominal = float_round(do.nominal, precision_digits=0, rounding_method='UP')
        # do_bop_paid = float_round(do.bop_paid, precision_digits=0, rounding_method='UP')
        
        if total_bop_count < 1:
            if additional_paid > do_nominal:
                raise UserError(_(
                    "BOP yang dibayarkan (%.2f) melebihi nominal DO (%.2f)."
                ) % (additional_paid, do.nominal))
        else:
            do_bop_paid = sum(do.bop_ids.mapped('amount_paid')) + additional_paid
            
            if do_bop_paid > do_nominal:
                raise UserError(_(
                    "Total BOP yang dibayarkan (%.2f) melebihi nominal DO (%.2f). "
                    "Periksa kembali persentase yang diinput."
                ) % (do_bop_paid, do_nominal))

    @api.depends('amount_paid', 'fleet_do_id.nominal')
    def compute_bop_line(self):
        for rec in self:
            if rec.fleet_do_id.nominal:
                rec.bop_percentage_paid = rec.amount_paid / rec.fleet_do_id.nominal

    @api.depends('amount_paid', 'fleet_do_id.nominal', 'fleet_do_id')
    def compute_bop_line_form(self):
        for rec in self:
            if rec.fleet_do_id.nominal:
                total_paid = sum(
                    rec.bop_ids.filtered(lambda bop: bop.state and bop.state in ('cancel', 'draft')).mapped('amount_paid'))
                rec.bop_percentage_paid_form = total_paid / rec.fleet_do_id.nominal
            else:
                rec.bop_percentage_paid_form = 0.0

    @api.onchange('fleet_do_id')
    def _onchange_fleet_do_id(self):

        if self.fleet_do_id:
            self.amount_paid = self.fleet_do_id.nominal - self.fleet_do_id.bop_paid
            self.origin_id = self.origin_id
            self.destination_id = self.destination_id
            self.bop_state = self.bop_state
            self.nominal = self.fleet_do_id.nominal
            if self.fleet_do_id.nominal > 0:
                self.bop_percentage_paid = sum(self.fleet_do_id.bop_ids.filtered(lambda bop: bop.state and bop.state in ('cancel', 'draft')).mapped('amount_paid')) / self.fleet_do_id.nominal

            self.bop_unpaid = self.fleet_do_id.nominal - self.fleet_do_id.bop_paid
            self.no_lambung = self.fleet_do_id.no_lambung
            self.bop_ids = [(6, 0, self.fleet_do_id.bop_ids.filtered(lambda x: x.amount_paid).ids)]
            self.review_ids = self.review_ids

    def action_approve_cashier(self):
        self.approval_date_cashier = fields.Date.today()
        self.approval_by_cashier = self.env.user.id
        self.state = 'approved_cashier'
        
        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', 'approved_cashier'),
            ('model', '=', self._name)
        ], limit=1)
        
        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")
        
        # === NEXT TIER ===
        next_state = 'approved_adh'
        nxt_def = self._tier_def(next_state)
        if nxt_def:
            # review = self._create_tier_review(next_state, 'Request to ADH')
            
            get_tier_definition_adh = self.env['tier.definition'].search([
                ('review_state', '=', 'approved_adh'),
                ('model', '=', self._name)
            ], limit=1)
            
            if not get_tier_definition_adh:
                raise UserError("Tier Definition for Administration Head belum dibuat")

            review = self.env['tier.review'].create({
                'res_id': self.id,
                'model': self._name,
                'name': "Request to Administration Head",
                'review_state': 'approved_adh',
                'status': 'pending',
                'requested_by': self.env.user.id,
                'comment': "Request to Administration Head",
                'definition_id': get_tier_definition_adh.id,
                'company_id': self.env.user.company_id.id,
                'sequence': 1,
            })
            
            reviewer = getattr(nxt_def, 'reviewer_id', False)
            if reviewer:
                self.current_reviewer_id = reviewer.id
                self._schedule_todo_for(
                    reviewer,
                    summary=_("Tier Approval: %s") % next_state,
                    note=_("Mohon approval untuk %s.") % (self.display_name,)
                )
            self.state = 'approved_cashier'
        else:
            self.state = 'approved_cashier'

        self.message_post(body=_("Approved by %s (Operation Cashier)") % self.env.user.name)
        return True

    def action_approve_adh(self):
        self.approval_date_cashier = fields.Date.today()
        self.approval_by_cashier = self.env.user.id
        self.state = 'approved_adh'
        
        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', 'approved_adh'),
            ('model', '=', self._name)
        ], limit=1)
        
        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")
        
        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'bop.line'),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'approved',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
                'comment': 'Approved by Administration Head',
            })
        
        # === NEXT TIER ===
        next_state = 'approved_by_kacab'
        nxt_def = self._tier_def(next_state)
        if nxt_def:
            # review = self._create_tier_review(next_state, 'Request to Kepala Cabang')
            
            get_tier_definition_kacab = self.env['tier.definition'].search([
                ('review_state', '=', 'approved_by_kacab'),
                ('model', '=', self._name)
            ], limit=1)
            
            if not get_tier_definition_kacab:
                raise UserError("Tier Definition for Kepala Cabang belum dibuat")

            review = self.env['tier.review'].create({
                'res_id': self.id,
                'model': self._name,
                'name': "Request to Kepala Cabang",
                'review_state': 'approved_by_kacab',
                'status': 'pending',
                'requested_by': self.env.user.id,
                'comment': "Request to Kepala Cabang",
                'definition_id': get_tier_definition_kacab.id,
                'company_id': self.env.user.company_id.id,
                'sequence': 1,
            })
            
            reviewer = getattr(nxt_def, 'reviewer_id', False)
            if reviewer:
                self.current_reviewer_id = reviewer.id
                self._schedule_todo_for(
                    reviewer,
                    summary=_("Tier Approval: %s") % next_state,
                    note=_("Mohon approval untuk %s.") % (self.display_name,)
                )
            self.state = 'approved_adh'
        else:
            self.state = 'approved_adh'

        self.message_post(body=_("Approved by %s (Administration Head)") % self.env.user.name)
        return True

    def action_approve_by_kacab(self):
        self.ensure_one()
        self.approval_date_by_kacab = fields.Date.today()
        self.approval_by_kacab= self.env.user.id
        self.state = 'approved_by_kacab'
        
        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', 'approved_by_kacab'),
            ('reviewer_id', '=', self.env.user.id),
            ('model', '=', 'bop.line')
        ], limit=1)

        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")
        
        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'bop.line'),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'approved',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
                'comment': 'Approved by Kepala Cabang',
            })

    def action_reject(self):
        reason = self.env.context.get('reject_reason')
        skip_comment = self.env.context.get('skip_comment_check')
        if not reason and not skip_comment and any(rec._is_comment_required_for_current_tier() for rec in self):
            return self._open_reject_wizard()
        
        for rec in self:

            review_state = _REVIEW_TARGET_BY_STATE_BOP.get(rec.state)
            if review_state:
                rec._reject_tier_review(review_state, rec._label_for_state(review_state), reason=reason)

            rec._close_all_todo_safe()

            rec.reject_by = self.env.user.id
            rec.reject_date = fields.Date.today()
            rec.state = 'cancel'

            body = _("Rejected by %s") % self.env.user.name
            if reason:
                body += _("<br/><b>Reason:</b> %s") % reason
            if reason and body:
                rec.reject_note = reason

            rec.message_post(body=body)
            
        return True
    
    def _is_comment_required_for_current_tier(self):
        self.ensure_one()
        tdef = self._tier_def_for_state(self.state)
        if not tdef:
            return False
        # beberapa instalasi beda nama field; cek yang umum
        for fname in ('has_comment', 'require_comment', 'need_comment'):
            if fname in tdef._fields and getattr(tdef, fname):
                return True
        return False
    
    def _open_reject_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bop.line.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Alasan Penolakan'),
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
            }
        }
        
    def _label_for_state(self, review_state):
        return {
            'draft': _('Operation Supervisor'),
            'approved_cashier': _('Cashier'),
            'approved_adh': _('Administration Head'),
            'approved_by_kacab': _('Kepala Cabang'),
        }.get(review_state, review_state)
        
    def _reject_tier_review(self, review_state, approval_label, reason=None):
        self.ensure_one()
        tdef = self._tier_def(review_state)
        if not tdef:
            raise UserError(_("Tier Definition untuk %s tidak ditemukan.") % review_state)

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', self._name),
            ('definition_id', '=', tdef.id)
        ], order='id desc', limit=1)

        if review:
            vals = {
                'status': 'rejected',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
            }
            if 'comment' in review._fields:
                comment = approval_label
                if reason:
                    comment = f"{approval_label} - {reason}"
                vals['comment'] = comment
            review.write(vals)
            
        self._close_my_todo_activity()
        self.current_reviewer_id = False
        self.message_post(body=_("Rejected by %s (%s)") % (self.env.user.name, review_state))
        return True

    def _tier_def_for_state(self, state):
        review_state = _REVIEW_TARGET_BY_STATE.get(state)
        if not review_state:
            return False
        TierDef = self.env['tier.definition']
        domain = [('review_state', '=', review_state)]
        if 'model_id' in TierDef._fields:
            domain.append(('model_id.model', '=', self._name))
        else:
            domain.append(('model', '=', self._name))
        return TierDef.search(domain, limit=1)
    
    def _close_all_todo_safe(self):
        todo = self.env.ref('mail.mail_activity_data_todo')
        acts = self.activity_ids.filtered(lambda a: a.activity_type_id.id == todo.id and not a.date_done)
        for act in acts:
            act.action_feedback(feedback=_("Rejected by %s") % self.env.user.name)
    
    def open_vendor_bill_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'create.vendor.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Create Vendor Bills',
            'context': {
                'default_bop_line_ids': [(6, 0, self.ids)],
            }
        }

    def _create_tier_review_bop(self, review_state, approval_label):
        self.ensure_one()

        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            ('model', '=', 'bop.line')
        ], limit=1)

        if not tier_definition:
            raise UserError(f"Tier definition with state '{review_state}' not found.")

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'bop.line'),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'approved',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
            })

        return review
    
    def _update_tier_review_bop(self, review_state, approval_label):
        self.ensure_one()

        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            # ('reviewer_id', '=', self.env.user.id),
            ('model', '=', 'bop.line')
        ], limit=1)

        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujuii permintaan ini")

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'bop.line'),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'approved',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
            })
        return review

    def _reject_tier_review_bop(self, review_state, approval_label):
        self.ensure_one()

        tier_definition = self.env['tier.definition'].search([
            ('review_state', '=', review_state),
            ('model', '=', 'bop.line')
        ], limit=1)

        if not tier_definition:
            raise UserError(f"Tier definition with state '{review_state}' not found.")

        review = self.env['tier.review'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'bop.line'),
            ('definition_id', '=', tier_definition.id)
        ], order='id desc', limit=1)

        if review:
            review.write({
                'status': 'rejected',
                'reviewed_date': fields.Datetime.now(),
                'done_by': self.env.user.id,
            })

        return review

    @api.depends('state')
    def _compute_review_ids_filtered(self):
        for record in self:
            allowed_states = [
                'approved_cashier',
                'approved_adh',
                'approved_by_kacab'
            ]

            record.review_ids = self.env['tier.review'].search([
                ('res_id', '=', record.id),
                ('model', '=', 'bop.line'),
                ('review_state', 'in', allowed_states),
            ])

    def open_approval_fleet_do_wizard(self):
        active_ids = self.env.context.get('active_ids') or []
        if not active_ids:
            raise UserError(_("Tidak ada baris BOP yang dipilih."))

        bop_lines = self.env['bop.line'].browse(active_ids).exists()
        if not bop_lines:
            raise UserError(_("Baris BOP yang dipilih tidak ditemukan."))

        fleet_do_ids = bop_lines.mapped('fleet_do_id').ids
        bop_line_ids = bop_lines.ids
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.fleet.do.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Submit Bulk Approval Delivery Order'),
            'context': {
                'default_fleet_do_ids': [(6, 0, fleet_do_ids)],
                'default_bop_line_ids': [(6, 0, bop_line_ids)],
            }
        }


    def open_reject_fleet_do_wizard(self):
        active_ids = self.env.context.get('active_ids') or []
        if not active_ids:
            raise UserError(_("Tidak ada baris BOP yang dipilih."))

        bop_lines = self.env['bop.line'].browse(active_ids).exists()
        if not bop_lines:
            raise UserError(_("Baris BOP yang dipilih tidak ditemukan."))

        fleet_do_ids = bop_lines.mapped('fleet_do_id').ids
        bop_line_ids = bop_lines.ids

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'reject.fleet.do.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Submit Bulk Reject Delivery Order / BOP'),
            'context': {
                'default_fleet_do_ids': [(6, 0, fleet_do_ids)],
                'default_bop_line_ids': [(6, 0, bop_line_ids)],
            }
        }

    @api.onchange('bop_state')
    def _onchange_bop_state(self):
        for rec in self:
            fleet_do = self.env['fleet.do'].search([('id', '=', rec.fleet_do_id.id)], limit=1)
            fleet_do.write({
                'bop_state': rec.bop_state
            })
        
    def do_action_approve_cashier(self):
        self.ensure_one()
        if not self.fleet_do_id:
            raise UserError(_("Baris ini tidak terkait Delivery Order."))
        
        ctx = dict(self.env.context, active_bop_line_id=self.id)
        return self.fleet_do_id.with_context(ctx).action_approve_cashier()

    def do_action_approve_adh(self):
        self.ensure_one()
        if not self.fleet_do_id:
            raise UserError("Baris ini tidak terkait Delivery Order.")
        # panggil action di DO
        return self.fleet_do_id.action_approve_adh()

    def do_action_approve_by_kacab(self):
        self.ensure_one()
        do = self.fleet_do_id
        if not do:
            raise UserError(_("Baris ini tidak terkait Delivery Order."))

        # (opsional) pre-check biar error lebih ramah sebelum ke method DO
        if do.state != 'approved_adh':
            raise UserError(_("DO belum di tahap approved Administration Head'."))

        if not do.geofence_loading_id or not do.geofence_unloading_id:
            raise UserError(_("Geofence Loading & Unloading di DO belum lengkap."))

        # panggil action di DO
        do.action_approve_by_kacab()

    def do_action_reject(self):
        dos = self.mapped('fleet_do_id').exists()
        if not dos:
            raise UserError(_("Baris ini tidak terkait Delivery Order."))

        return dos.action_reject()
    
    def open_addtional_cost_wizard(self):
        self.ensure_one()
        do_id = self.fleet_do_id.id
        if not do_id:
            raise UserError("Baris BOP belum terkait DO.")

        ctx = dict(self.env.context, default_fleet_do_id=do_id)
        print(ctx, self.fleet_do_id, do_id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bop.additional.cost.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Biaya Tambahan BOP',
            'context': ctx,   # active_id/active_model otomatis ikut dari self
        }


class CreateVendorBillWizard(models.TransientModel):
    _name = 'create.vendor.bill.wizard'
    _description = 'Wizard to create vendor bills from BOP Lines'

    bop_line_ids = fields.Many2many('bop.line', string="BOP Lines")
    order_count = fields.Integer(string="Order Count", compute="_compute_order_count", store=False)

    @api.depends('bop_line_ids')
    def _compute_order_count(self):
        for wizard in self:
            wizard.order_count = len(wizard.bop_line_ids)

    def action_create_vendor_bills(self):
        bop_lines = self.bop_line_ids.filtered(lambda l: l.driver_id)
        if not bop_lines:
            return

        if any(bop_lines.mapped('is_created_vendor_bill')):
            raise UserError("BOP ini sudah dibuat vendor bill!")

        not_exported = bop_lines.filtered(lambda l: not l.is_exported_to_mcm)
        if not_exported:
            raise UserError("Masih ada baris BOP yang belum di-export ke MCM!")

        not_approved = bop_lines.filtered(lambda l: l.state != 'approved_by_kacab')
        if not_approved:
            bop_nomor = ', '.join(not_approved.mapped('bop_no'))
            raise UserError(f"Masih ada baris BOP yang belum disetujui oleh Kepala Cabang! Nomor BOP: {bop_nomor}")

        cancelled_bops = bop_lines.filtered(lambda l: l.state == 'cancel')
        if cancelled_bops:
            cancelled_names = ', '.join(cancelled_bops.mapped('bop_no'))
            raise UserError(f"Nomor BOP berikut statusnya 'cancel': {cancelled_names}")
        
        expense_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_prepayments'),
            ('code', '=', '11410040'),
            # ('company_id', 'in', self.env.context.get('allowed_company_ids'))
        ], limit=1)
        
        if not expense_account:
            raise ValidationError(_("Tidak ditemukan akun expense di company ini."))

        # Ambil semua driver_id dari bop_lines
        drivers = bop_lines.mapped('driver_id')
        drivers = [d for d in drivers if d]

        if not drivers:
            raise UserError("Tidak ada driver yang ditemukan pada baris BOP.")

        # Cek apakah semua driver sama
        first_driver = drivers[0]
        if all(d.id == first_driver.id for d in drivers):
            partner = first_driver
        else:
            domain = [('header_bop', '=', True)]
            existing = self.env['res.partner'].search(domain, limit=1)
            if not existing:
                raise UserError(
                    "Belum ada partner yang ditandai sebagai 'Header BOP'. Silakan centang satu driver di menu Mitra.")
            partner = existing

        # bop_names = ", ".join(bop_lines.mapped('bop_no'))
        bop_do_pairs = [f"{line.bop_no} - {line.fleet_do_id.name}" for line in bop_lines]
        bop_do_display = ", ".join(bop_do_pairs)
        total_bop_value = sum(bop_lines.mapped('amount_paid'))

        driver_vehicle_set = set()
        for line in bop_lines:
            if line.driver_id and line.fleet_do_id:
                key = f"{line.driver_id.name} - {line.fleet_do_id.vehicle_id.license_plate}"
                driver_vehicle_set.add(key)

        driver_info_display = ", ".join(sorted(driver_vehicle_set))

        invoice_lines = []
        do_ids = []
        for line in bop_lines:
            do_ids.append(line.fleet_do_id)
            name_line = f"{line.bop_no} - {line.fleet_do_id.name}"
            price_unit = line.amount_paid or 0.0

            fleet_do = line.fleet_do_id
            do_vehicle_id = fleet_do.vehicle_id

            analytic_account = self.env['account.move']._get_or_create_analytic_account((
                do_vehicle_id.vehicle_name if do_vehicle_id else fleet_do.delivery_category_id.name,
                '',
                '',
                do_vehicle_id.no_lambung if do_vehicle_id else fleet_do.product_category_id.name,
                do_vehicle_id.product_category_id.name if do_vehicle_id else fleet_do.product_category_id.name,
                do_vehicle_id.category_id.name if do_vehicle_id else fleet_do.delivery_category_id.name
            ))
            analytic_distribution = None
            if analytic_account:
                analytic_distribution = {str(analytic_account.id): 100}

            invoice_lines_payload = {
                'name': name_line,
                'quantity': 1,
                'price_unit': price_unit,
                # 'account_id': expense_account.id,
                'currency_id': self.env.user.company_id.currency_id.id
            }
            second_payload = None

            if (
                line.fleet_do_id.bop_driver_used
                and line.fleet_do_id.bop_driver_used > 0
                and not line.fleet_do_id.remaining_bop_driver_has_been_converted_to_bill
            ):
                remaining_bop_account = self.env['account.account'].search([
                    ('is_for_driver_remaining_bop', '=', True),
                ], limit=1)

                if not remaining_bop_account:
                    raise UserError(_('Akun untuk Sisa BOP Driver tidak ditemukan. Pastikan ada akun dengan flag "is_for_driver_remaining_bop" = True.'))

                second_payload = {
                    'name': 'Sisa BOP Driver',
                    'quantity': 1,
                    'price_unit': line.fleet_do_id.bop_driver_used,
                    'account_id': remaining_bop_account.id,
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'is_for_journal_remaining_bop': True,
                }
                line.fleet_do_id.remaining_bop_driver_has_been_converted_to_bill = True


            if analytic_distribution:
                invoice_lines_payload['analytic_distribution'] = analytic_distribution
                if second_payload:
                    second_payload['analytic_distribution'] = analytic_distribution

            invoice_lines.append((0, 0, invoice_lines_payload))
            if second_payload:
                invoice_lines.append((0, 0, second_payload))

        bill_vals = {
            'move_type': 'in_invoice',
            'narration': driver_info_display,
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'ref': bop_do_display,
            'invoice_origin': bop_do_display,
            'company_id': self.env.user.company_id.id,
            'invoice_line_ids': invoice_lines,
        }

        # if bop_lines:
        #     bop_lines.write({'is_created_vendor_bill': True})

        bill = self.env['account.move'].create(bill_vals)
        # bop_lines.write({'vendor_bill_id': bill.id, 'is_created_vendor_bill': True})

        query_update = """
        UPDATE account_move_line
        SET account_id = %s
        WHERE move_id = %s AND display_type = 'product' AND is_for_journal_remaining_bop IS FALSE
        """
        _logger.info(f"On Update Account ID in Bill Line -> {query_update, (expense_account.id, bill.id)}")
        self.env.cr.execute(query_update, (expense_account.id, bill.id))

        if self.env.company.portfolio_id.name != 'Frozen':
            for do in do_ids:
                if do:
                    order_ids = [line.order_id.id for line in do.po_line_ids]
                    orders = self.env['sale.order'].browse(order_ids)

                    for order in orders:
                        no_surat_jalan_list = order.order_line._collect_no_surat_jalan()
                        filtered_order_line = order.order_line.filtered(lambda r: r.no_surat_jalan and r.do_id)

                        for order_line in filtered_order_line:
                            filtered_order_line._update_related_records(order_line, no_surat_jalan_list)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
        }

class TierReviewInFleetDo(models.Model):
    _inherit = 'tier.review'

    review_state = fields.Char(
        string="Review State of DO",
        index=True,
    )

class TierDefinition(models.Model):
    _inherit = "tier.definition"

    REVIEW_STATES = [
        ('approved_operation_spv', 'Approved by Operation Supervisor'),
        ('approved_cashier', 'Approved by Cashier'),
        ('approved_adh', 'Approved by Administration Head'),
        ('approved_by_kacab', 'Approved by Kepala Cabang'),
    ]

    review_state = fields.Selection(
        selection=REVIEW_STATES,
        string="Review State of DO",
        index=True,
    )
    show_review_state = fields.Boolean(compute="_compute_show_review_state")

    @api.depends('model_id')
    def _compute_show_review_state(self):
        for rec in self:
            rec.show_review_state = rec.model_id.model in ['fleet.do', 'bop.line']


STATE_MAP = {
    'fleet.do': {
        'approved_operation_spv': ('to_approve',          'action_approve_operation_spv'),
        'approved_cashier':       ('approved_operation_spv','action_approve_cashier'),
        'approved_adh':           ('approved_cashier',     'action_approve_adh'),
        'approved_by_kacab':      ('approved_adh',         'action_approve_by_kacab'),
    },
    'bop.line': {
        # settlement flow
        'approved_cashier':       ('approved_operation_spv','action_approve_cashier'),
        'approved_adh':           ('approved_cashier',     'action_approve_adh'),
        'approved_by_kacab':      ('approved_adh',         'action_approve_by_kacab'),
    },
}

ALLOWED_REJECT_STATES_DO = {
    'to_approve', 'approved_operation_spv', 'approved_cashier', 'approved_adh', 'approved_by_kacab'
}
ALLOWED_REJECT_STATES_BOP = {'approved_cashier', 'approved_adh'}

class ApprovalFleetDoWizard(models.TransientModel):
    _name = 'approval.fleet.do.wizard'
    _description = 'Bulk Approval Fleet DO'

    fleet_do_ids = fields.Many2many('fleet.do', string="DO Number")
    bop_line_ids = fields.Many2many('bop.line', string="BOP Number")
    order_count_do = fields.Integer(string="Order Count DO", compute="_compute_order_count_do", store=False)
    order_count_bop = fields.Integer(string="Order Count BOP", compute="_compute_order_count_bop", store=False)

    @api.depends('fleet_do_ids')
    def _compute_order_count_do(self):
        for wizard in self:
            wizard.order_count_do = len(wizard.fleet_do_ids)
            
    @api.depends('bop_line_ids')
    def _compute_order_count_bop(self):
        for wizard in self:
            wizard.order_count_bop = len(wizard.bop_line_ids)
            
    def _get_reviewer_state(self, model_name):
        tier = self.env['tier.definition'].search([
            ('reviewer_id', '=', self.env.user.id),
            ('model', '=', model_name),
        ], limit=1)
        if not tier:
            raise UserError(_("Anda tidak memiliki akses untuk menyetujui %s.") % model_name)
        return tier.review_state
    
    # ---- Helper generik bulk approval
    def _bulk_approve(self, records, model_name, *, prefilter=None, label='record', validate_state=True):
        """records: recordset target (fleet.do / bop.line)
        model_name: 'fleet.do' / 'bop.line'
        prefilter: callable optional untuk filter tambahan (mis. settlement saja)
        label: teks untuk error
        validate_state: True = cek state saat ini, False = lewati cek"""
        if prefilter:
            records = records.filtered(prefilter)
        if not records:
            return 0

        review_state = self._get_reviewer_state(model_name)
        state_map = STATE_MAP.get(model_name, {})
        if review_state not in state_map:
            raise UserError(_("State review %s tidak dikenali untuk %s.") % (review_state or '-', model_name))

        expected_state, method_name = state_map[review_state]

        # cek state hanya jika diminta
        if validate_state:
            invalid = records.filtered(lambda r: r.state != expected_state)
            if invalid:
                raise UserError(_("%s tidak berada di state '%s'. Silakan cek kembali.") % (label, expected_state))

        # pastikan method ada
        if not hasattr(records, method_name) and not hasattr(self.env[model_name], method_name):
            raise UserError(_("Method approval '%s' belum dibuat di model %s.") % (method_name, model_name))

        for rec in records:
            getattr(rec, method_name)()

        return len(records)


    def action_bulk_approval_delivery_order(self):
        # Ambil semua BOP yang dipilih di wizard
        bop_lines = self.bop_line_ids.exists()
        if not bop_lines:
            raise UserError(_("Tidak ada BOP yang dipilih."))

        # Pisahkan settlement vs non-settlement
        bop_settlements = bop_lines.filtered('is_settlement')
        bop_additional_cost = bop_lines.filtered('is_additional_cost')
        # bop_general = bop_lines - bop_settlements
        bop_general = bop_lines - bop_settlements - bop_additional_cost

        cnt_bop = cnt_do = 0

        # 1) Settlement → jalankan approval di model bop.line (tanpa cek state)
        if bop_settlements:
            
            cnt_bop = self._bulk_approve(
                bop_settlements, 'bop.line',
                label=_("BOP settlement"),
                validate_state=False,      # lewati cek state untuk BOP
            )
            
        if bop_additional_cost:
            
            cnt_bop = self._bulk_approve(
                bop_additional_cost, 'bop.line',
                label=_("BOP Additional Cost"),
                validate_state=False,      # lewati cek state untuk BOP
            )

        # 2) Non-settlement → approve DO yang terkait (cek state DO)
        if bop_general:
            do_set = bop_general.mapped('fleet_do_id').exists()
            if not do_set:
                raise UserError(_("BOP non-settlement yang dipilih tidak memiliki DO."))
            cnt_do = self._bulk_approve(
                do_set, 'fleet.do',
                label=_("Delivery Order"),
                validate_state=True,       # DO harus di state yang tepat
            )

        # Notifikasi ringkas
        msg = _("Approval berhasil. DO: %(a)d, BOP: %(b)d") % {'a': cnt_do, 'b': cnt_bop}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Berhasil'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
        
class RejectFleetDoWizard(models.TransientModel):
    _name = 'reject.fleet.do.wizard'
    _description = 'Bulk Reject Fleet DO / BOP'

    fleet_do_ids = fields.Many2many('fleet.do', string="DO Number")
    bop_line_ids = fields.Many2many('bop.line', string="BOP Number")
    order_count_do = fields.Integer(string="Order Count DO", compute="_compute_order_count_do", store=False)
    order_count_bop = fields.Integer(string="Order Count BOP", compute="_compute_order_count_bop", store=False)

    @api.depends('fleet_do_ids')
    def _compute_order_count_do(self):
        for wizard in self:
            wizard.order_count_do = len(wizard.fleet_do_ids)
            
    @api.depends('bop_line_ids')
    def _compute_order_count_bop(self):
        for wizard in self:
            wizard.order_count_bop = len(
                wizard.bop_line_ids.filtered(lambda l: l.fleet_do_id and l.fleet_do_id.vehicle_id.asset_type == 'asset')
            )

    ALLOWED_REJECT_STATES_BOP = {'approved_operation_spv', 'approved_cashier', 'approved_adh'}
    ALLOWED_REJECT_STATES_DO = {'to_approve', 'approved_operation_spv', 'approved_cashier', 'approved_adh'}

    # di comment sementar untuk comment bulk reject
    # def _tier_def_for_state(self, state):
    #     review_state = _REVIEW_TARGET_BY_STATE.get(state)
    #     if not review_state:
    #         return False
    #     TierDef = self.env['tier.definition']
    #     domain = [('review_state', '=', review_state)]
    #     if 'model_id' in TierDef._fields:
    #         domain.append(('model_id.model', '=', self._name))
    #     else:
    #         domain.append(('model', '=', self._name))
    #     return TierDef.search(domain, limit=1)

    # di comment sementar untuk comment bulk reject
    # def _is_comment_required_for_current_tier(self):
    #     self.ensure_one()
    #     tdef = self._tier_def_for_state(self.state)
    #     if not tdef:
    #         return False
    #     # beberapa instalasi beda nama field; cek yang umum
    #     for fname in ('has_comment', 'require_comment', 'need_comment'):
    #         if fname in tdef._fields and getattr(tdef, fname):
    #             return True
    #     return False

    def action_bulk_reject_delivery_order(self):
        reason = self.env.context.get('reject_reason')
        if reason is None:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'bulk.reject.reason.wizard',
                'view_mode': 'form',
                'target': 'new',
                'name': _('Alasan Penolakan'),
                'context': {
                    'active_model': self._name,
                    'active_ids': self.ids,
                }
            }

        # Kumpulkan semua input dari wizard
        do_set = self.fleet_do_ids.exists()
        bop_set = self.bop_line_ids.exists()

        if not do_set and not bop_set:
            raise UserError(_("Tidak ada DO/BOP yang dipilih."))

        # Pisahkan BOP settlement vs non-settlement
        bop_settlement = bop_set.filtered('is_settlement')
        bop_non_settlement = bop_set - bop_settlement

        # Non-settlement BOP → tambahkan DO-nya ke do_set
        if bop_non_settlement:
            do_set |= bop_non_settlement.mapped('fleet_do_id').exists()

        # --------------- Reject BOP settlement (jika ada) ---------------
        if bop_settlement:
            # (opsional) tier check untuk BOP
            tier_bop = self.env['tier.definition'].search([
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', 'bop.line'),
            ], limit=1)
            if not tier_bop:
                raise UserError(_("Anda tidak memiliki akses untuk menolak BOP settlement."))

            invalid_bops = bop_settlement.filtered(lambda b: b.state not in ALLOWED_REJECT_STATES_BOP)
            if invalid_bops:
                raise UserError(_("Ada BOP settlement yang tidak bisa direject dari state saat ini: %s") %
                                ", ".join(invalid_bops.mapped(lambda r: r.bop_no or f"ID {r.id}")))
            # Eksekusi reject BOP
            for b in bop_settlement:
                if not hasattr(b, 'action_reject'):
                    raise UserError(_("Model bop.line tidak memiliki method action_reject."))
                with self.env.cr.savepoint():
                    b.with_context(reject_reason=reason).action_reject()

        # --------------- Reject DO (langsung & hasil map dari BOP non-settlement) ---------------
        do_done = 0
        if do_set:

            # (opsional) tier check untuk DO
            tier_do = self.env['tier.definition'].search([
                ('reviewer_id', '=', self.env.user.id),
                ('model', '=', 'fleet.do'),
            ], limit=1)
            if not tier_do:
                # kalau kamu tidak pakai tier di DO, boleh dihapus blok ini
                raise UserError(_("Anda tidak memiliki akses untuk menolak Delivery Order."))

            invalid_dos = do_set.filtered(lambda d: d.state not in ALLOWED_REJECT_STATES_DO)
            if invalid_dos:
                # tidak langsung raise; kita kasih info & tetap proses yang valid
                self.env.user.notify_warning(
                    message=_("Beberapa DO dilewati karena state tidak diperbolehkan: %s") %
                            ", ".join(invalid_dos.mapped('name')),
                    title=_("Info"),
                    sticky=False
                )

            valid_dos = (do_set - invalid_dos)
            # tutup activity TODO milik user pada DO yg valid lalu reject
            todo = self.env.ref('mail.mail_activity_data_todo')
            for d in valid_dos:
                with self.env.cr.savepoint():
                    acts = d.activity_ids.filtered(
                        lambda a: a.activity_type_id.id == todo.id and a.user_id.id == self.env.user.id and not a.date_done
                    )
                    for act in acts:
                        act.action_feedback(feedback=_("Rejected via bulk by %s") % self.env.user.name)

                    d.with_context(reject_reason=reason).action_reject()

                    if d.state == 'cancel':
                        do_done += 1

        # Notifikasi
        msg = _("Reject selesai. DO diproses: %(do)d, BOP settlement: %(bop)d") % {
            'do': do_done, 'bop': len(bop_settlement)
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Berhasil'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


# class RejectFleetDoWizard(models.TransientModel):
#     _name = 'reject.fleet.do.wizard'
#     _description = 'Bulk Reject Fleet DO'

#     bop_line_ids = fields.Many2many('fleet.do', string="DO Number")
#     order_count = fields.Integer(string="Order Count", compute="_compute_order_count", store=False)

#     @api.depends('bop_line_ids')
#     def _compute_order_count(self):
#         for wizard in self:
#             wizard.order_count = len(wizard.bop_line_ids)

#     def action_bulk_reject_delivery_order(self):
#         if not self.bop_line_ids:
#             raise UserError("Tidak ada Delivery Order yang dipilih.")

#         # Optional: Cek apakah user berhak reject berdasarkan tier.definition
#         tier_definition = self.env['tier.definition'].search([
#             ('reviewer_id', '=', self.env.user.id),
#             ('model', '=', 'fleet.do'),
#         ], limit=1)

#         if not tier_definition:
#             raise UserError("Anda tidak memiliki akses untuk menolak permintaan ini")

#         # Dapatkan state yang seharusnya bisa direject oleh user ini
#         allowed_states = [
#             'to_approve',
#             'approved_operation_spv',
#             'approved_cashier',
#             'approved_adh',
#             'approved_by_kacab',
#         ]

#         # Filter hanya yang state-nya sesuai
#         invalid_dos = self.bop_line_ids.filtered(lambda line: line.state not in allowed_states)
#         if invalid_dos:
#             raise UserError("Terdapat Delivery Order yang tidak bisa direject di state saat ini.")

#         # Jalankan reject satu per satu
#         for line in self.bop_line_ids:
#             # line = line.fleet_do_id
#             if line and hasattr(line, 'action_reject'):
#                 line.action_reject()
#             else:
#                 raise UserError("Delivery Order tidak memiliki method reject.")

class ApprovalSpvFleetDoWizard(models.TransientModel):
    _name = 'approval.spv.fleet.do.wizard'
    _description = 'Bulk Approval SPV Fleet DO'

    bop_line_ids = fields.Many2many('fleet.do', string="DO Number")
    order_count = fields.Integer(string="Order Count", compute="_compute_order_count", store=False)

    @api.depends('bop_line_ids')
    def _compute_order_count(self):
        for wizard in self:
            wizard.order_count = len(wizard.bop_line_ids)

    def action_bulk_spv_approval_delivery_order(self):
        tier_definition = self.env['tier.definition'].search([
            ('reviewer_id', '=', self.env.user.id),
            ('model', '=', 'fleet.do'),
        ], limit=1)

        if not tier_definition:
            raise UserError("Anda tidak memiliki akses untuk menyetujui permintaan ini")
        
        
        allowed_states = {
            'approved_cashier': 'Cashier',
            'approved_adh': 'Administration Head',
            'approved_by_kacab': 'Kepala Cabang',
        }

        review_state = tier_definition.review_state
        if review_state in allowed_states:
            raise UserError(_(
                "Proses approval untuk '%s' hanya dapat dilakukan melalui menu *BOP List*."
            ) % allowed_states[review_state])

        state = ''
        method_name = ''
        if review_state == 'approved_operation_spv':
            state = 'to_approve'
            method_name = 'action_approve_operation_spv'
        

        invalid_dos = self.bop_line_ids.filtered(lambda do: do.state != state)
        if invalid_dos:
            bop_ids = invalid_dos.bop_ids
            if not all(bop.is_additional_cost for bop in bop_ids):
                raise UserError(
                    _("Terdapat Delivery Order yang tidak berada di state '%s'. Silakan cek kembali.") % state
                )

        if not hasattr(self.env['fleet.do'], method_name):
            raise UserError("Method approval '%s' belum dibuat di model fleet.do" % method_name)

        for do in self.bop_line_ids:
            getattr(do, method_name)()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil',
                'message': 'Approval berhasil dilakukan.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

class RejectSpvFleetDoWizard(models.TransientModel):
    _name = 'reject.spv.fleet.do.wizard'
    _description = 'Bulk Reject Fleet DO'

    bop_line_ids = fields.Many2many('fleet.do', string="DO Number")
    order_count = fields.Integer(string="Order Count", compute="_compute_order_count", store=False)

    @api.depends('bop_line_ids')
    def _compute_order_count(self):
        for wizard in self:
            wizard.order_count = len(wizard.bop_line_ids)

    # def action_bulk_spv_reject_delivery_order(self):
    #     if not self.bop_line_ids:
    #         raise UserError("Tidak ada Delivery Order yang dipilih.")
    #     print(self._name)
    #     print(self.ids)
    #     reason = self.env.context.get('reject_reason')
    #     print(reason)
    #     if reason is None:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'bulk.reject.spv.reason.wizard',
    #             'view_mode': 'form',
    #             'target': 'new',
    #             'name': _('Alasan Penolakan'),
    #             'context': {
    #                 'active_model': self._name,
    #                 'active_ids': self.ids,
    #             }
    #         }

    #     # Optional: Cek apakah user berhak reject berdasarkan tier.definition
    #     tier_definition = self.env['tier.definition'].search([
    #         ('reviewer_id', '=', self.env.user.id),
    #         ('model', '=', 'fleet.do'),
    #     ], limit=1)

    #     if not tier_definition:
    #         raise UserError("Anda tidak memiliki akses untuk menolak permintaan ini")
        
    #     allowed_states = {
    #         'approved_cashier': 'Cashier',
    #         'approved_adh': 'Administration Head',
    #         'approved_by_kacab': 'Kepala Cabang',
    #     }

    #     review_state = tier_definition.review_state
    #     if review_state in allowed_states:
    #         raise UserError(_(
    #             "Proses reject untuk '%s' hanya dapat dilakukan melalui menu *BOP List*."
    #         ) % allowed_states[review_state])

    #     # Dapatkan state yang seharusnya bisa direject oleh user ini
    #     allowed_states = [
    #         'to_approve',
    #         'approved_operation_spv',
    #         'approved_cashier',
    #         'approved_adh',
    #         'approved_by_kacab',
    #     ]

    #     # Filter hanya yang state-nya sesuai
    #     invalid_dos = self.bop_line_ids.filtered(lambda line: line.state not in allowed_states)
    #     if invalid_dos:
    #         raise UserError("Terdapat Delivery Order yang tidak bisa direject di state saat ini.")

    #     # Jalankan reject satu per satu
    #     for line in self.bop_line_ids:
    #         if line and hasattr(line, 'action_reject'):
    #             print("TEST")
    #             # line.with_context(skip_comment_check=True).action_reject()
    #             line.with_context(reject_reason=reason).action_reject()

    #         else:
    #             raise UserError("Delivery Order tidak memiliki method reject.")
    
    def action_bulk_spv_reject_delivery_order(self):
        self.ensure_one()
        
        reason = self.env.context.get('reject_reason')
        if not reason:
            # buka wizard alasan, bawa context agar wizard tahu siapa parent
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'bulk.reject.spv.reason.wizard',
                'view_mode': 'form',
                'target': 'new',
                'name': _('Alasan Penolakan'),
                'context': {
                    'active_model': self._name,
                    'active_ids': self.ids,
                },
            }
        # --- Permission check (sesuaikan modelnya) ---
        tier_definition = self.env['tier.definition'].search([
            ('reviewer_id', '=', self.env.user.id),
            ('model', '=', 'fleet.do'),  # atau 'fleet.do' bila memang HARUS DO
        ], limit=1)
        if not tier_definition:
            raise UserError(_("Anda tidak memiliki akses untuk menolak permintaan ini."))

        # --- Batasi level yang harus via BOP List ---
        lock_by_level = {
            'approved_cashier': 'Cashier',
            'approved_adh': 'Administration Head',
            'approved_by_kacab': 'Kepala Cabang',
        }
        review_state = tier_definition.review_state
        if review_state in lock_by_level:
            raise UserError(_("Proses reject untuk '%s' hanya dapat dilakukan melalui menu BOP List.") % lock_by_level[review_state])

        # --- Validasi state yang boleh ditolak oleh SPV ---
        allowed_states = ['to_approve', 'approved_operation_spv']
        invalid = self.bop_line_ids.filtered(lambda l: getattr(l, 'state', False) not in allowed_states)
        if invalid:
            raise UserError(_("Ada Delivery Order yang tidak bisa direject pada state saat ini."))

        # --- Eksekusi reject ---
        for line in self.bop_line_ids:
            # ganti ke relasi yang benar jika method reject ada di DO
            target = line  # atau line.do_id
            if not hasattr(target, 'action_reject'):
                raise UserError(_("Delivery Order tidak memiliki method reject."))
            target.with_context(reject_reason=reason).action_reject()

        # Opsional: kasih notifikasi
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Reject selesai"),
                'message': _("%s DO berhasil direject.") % len(self.bop_line_ids),
                'sticky': False,
                'type': 'warning',
            }
        }

            
class BopSaveSuccessWizard(models.TransientModel):
    _name = 'bop.save.success.wizard'
    _description = 'Notifikasi Simpan BOP'

    bop_id = fields.Many2one('bop.line', readonly=True)
    message = fields.Text(default="Data tersimpan.")

    def action_open_bop(self):
        self.ensure_one()
        if not self.bop_id:
            raise UserError(_("BOP tidak ditemukan."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOP'),
            'res_model': 'bop.line',
            'view_mode': 'form',
            'res_id': self.bop_id.id,
            'target': 'current',
        }
        
class FleetDoRejectWizard(models.TransientModel):
    _name = 'fleet.do.reject.wizard'
    _description = 'Reject Reason'

    reason = fields.Text(string='Alasan Reject', required=True)

    def action_confirm(self):
        recs = self.env[self.env.context.get('active_model')].browse(self.env.context.get('active_ids', []))
        recs.with_context(reject_reason=self.reason).action_reject()
        return {'type': 'ir.actions.act_window_close'}
    
class BopLineRejectWizard(models.TransientModel):
    _name = 'bop.line.reject.wizard'
    _description = 'Reject Reason'

    reason = fields.Text(string='Alasan Reject', required=True)

    def action_confirm(self):
        recs = self.env[self.env.context.get('active_model')].browse(self.env.context.get('active_ids', []))
        recs.with_context(reject_reason=self.reason).action_reject()
        return {'type': 'ir.actions.act_window_close'}
    
class BulkRejectReasonWizard(models.TransientModel):
    _name = 'bulk.reject.reason.wizard'
    _description = 'Alasan Bulk Reject'

    reason = fields.Text(string='Alasan', required=True)

    def action_confirm(self):
        # jalankan ulang method bulk di wizard pemanggil, bawa reason
        parent_model = self.env.context.get('active_model')
        parent_ids = self.env.context.get('active_ids', [])
        parent = self.env[parent_model].browse(parent_ids)
        return parent.with_context(reject_reason=self.reason).action_bulk_reject_delivery_order()
    
class BulkRejectSpvReasonWizard(models.TransientModel):
    _name = 'bulk.reject.spv.reason.wizard'
    _description = 'Alasan Bulk Reject'

    reason = fields.Text(string='Alasan', required=True)

    def action_confirm(self):
        self.ensure_one()
        parent_model = self.env.context.get('active_model')
        parent_ids   = self.env.context.get('active_ids') or []
        if not parent_model or not parent_ids:
            raise UserError(_("Context tidak lengkap: active_model/active_ids hilang."))

        parent = self.env[parent_model].browse(parent_ids)
        # jalankan parent method dengan reason dari wizard
        parent.with_context(reject_reason=self.reason).action_bulk_spv_reject_delivery_order()

        # tutup wizard
        return {'type': 'ir.actions.act_window_close'}

