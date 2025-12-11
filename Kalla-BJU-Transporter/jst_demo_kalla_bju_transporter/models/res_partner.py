# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models, api, _
from datetime import timedelta, date
from odoo.exceptions import ValidationError
from odoo.tools import UserError
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'portfolio.view.mixin']

    customer_code = fields.Char('Customer Code', size=18, tracking=True)
    nid = fields.Char('NID', tracking=True)
    customer_ids = fields.Many2many('res.partner',relation="driver_customer_rel",column1="id1", column2="id2", string='Customer Unit Kerja',domain=[('is_customer', '=', True)], tracking=True)
    customer_product_ids = fields.Many2many('product.customer', relation="customer_product_rel", column1="customer_id", column2="product_customer_id",
                                    string='Product Customer', tracking=True)
    customer_category = fields.Selection([('C', 'Corporate'), ('R', 'Retail')])
    customer_group = fields.Selection([('swasta', 'Swasta'), ('bumn', 'BUMN'),('bumd', 'BUMD'),('pemerintahan', 'Pemerintahan'),('perorangan', 'Perorangan')])
    # product_filter_id = fields.Many2one('product.category',
    #                                       domain= [('name', 'in', ['Transporter', 'VLI', 'Trucking'])], required=True)
    product_filter_ids = fields.Many2many('product.category', relation="customer_product_filter_rel",
                                          column1="customer_id", column2="product_category_id",
                                          string='Product Filter', tracking=True)
    bank_cash = fields.Many2one('account.journal', 'Bank / Cash')
    rekening_number = fields.Char('No. Rekening')
    rekening_name = fields.Char('Nama Rekening')
    bank_name = fields.Many2one('res.partner.bank', 'Nama Bank')
    ktp = fields.Char('KTP')
    tax_id_address = fields.Char('Tax ID Address')
    no_driving_license = fields.Char('NO Driving License', readonly=True)
    is_driver = fields.Boolean()
    is_customer = fields.Boolean()
    availability = fields.Selection([('Ready', 'Ready'),('On Duty', 'On Duty'), ('Sakit', 'Sakit'), ('Cuti', 'Cuti'), ('Absent', 'Absent')], tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle','Armada')
    # value_contract = fields.Monetary('Nilai Kontrak', currency_field='currency_id', tracking=True)
    # date_contract = fields.Date('Tanggal Kontrak', tracking=True)
    # end_date_contract = fields.Date('Tanggal Berakhir Kontrak', tracking=True)
    # file_contract = fields.Binary("Upload File Kontrak")
    # file_contract_name = fields.Char("Nama File Kontrak")
    license_expiry = fields.Date(string="Masa Berlaku SIM",domain= [('is_driver', 'in', True)], required=True)
    is_license_expiring = fields.Boolean(string="SIM Akan Kedaluwarsa", compute="_compute_license_expiry", store=True)
    diciplinary_count = fields.Integer(string="Diciplinary Count", compute="compute_diciplinary_count", readonly=True, store=False)
    emp_violation_ids = fields.One2many('disicplinary.line', 'partner_id', string="Disciplinary Records")
    is_vendor = fields.Boolean()
    supplier_site = fields.Char()
    header_bop = fields.Boolean(string="Header Bop")
    bank_name_ids = fields.One2many('res.partner.bank', 'partner_id')
    employee_link_ids = fields.One2many(
        'hr.employee', 'partner_id',
        string='Linked Employees', readonly=True
    )
    is_tam = fields.Boolean(string="is TAM", help="Jika dicentang artinya customer adalah TAM")

    ownership_driver_id = fields.Many2one(
        'res.partner', string='Ownership Driver',
        compute='_compute_ownership_driver_id',
        store=True, compute_sudo=True, readonly=True
    )
    account_name_number = fields.Char(
        compute='_compute_account_name_number',
        store=True,
        readonly=True,
        index=True,
    )
    tax_invoicing_method = fields.Selection([
        ('total_invoice', 'Total Invoice'),
        ('line_invoice', 'Line Invoice'),
    ], default='total_invoice', tracking=True)
    partner_tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        store=True, readonly=False, precompute=True,
        context={'active_test': False},
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    license_type = fields.Char('Jenis SIM', readonly=True)

    def unlink(self):
        for partner in self:
            sale_orders = self.env['sale.order'].search([
                '|',
                ('partner_invoice_id', '=', partner.id),
                ('partner_shipping_id', '=', partner.id)
            ])
            _logger.info(f"Sale Order yang ditemukan: ({len(sale_orders)}) {sale_orders}")
            if sale_orders:
                raise UserError(f'Partner ini masih digunakan di Sale Order (id: {", ".join(sale_orders.mapped("id"))}), tidak dapat dihapus.')
        return super().unlink()


    @api.depends(
        'bank_name_ids.acc_number',
        'bank_name_ids.bank_id',
        'bank_name_ids.bank_id.name',
        'bank_name_ids.active',
    )
    def _compute_account_name_number(self):
        for partner in self:
            lines = partner.bank_name_ids if 'bank_name_ids' in partner._fields else partner.bank_ids
            lines = lines.filtered(lambda l: getattr(l, 'active', True))

            if not lines:
                partner.account_name_number = False
                continue

            try:
                top = lines.sorted(lambda r: (getattr(r, 'sequence', 0), r.id))[0]
            except Exception:
                top = lines[0]

            num = (top.acc_number or '').strip()
            bank = (top.bank_id and top.bank_id.name) or (getattr(top, 'bank_name', '') or '')
            partner.account_name_number = f"{num} - {bank}" if (num and bank) else (num or bank or False)

    @api.depends('employee_link_ids.ownership_driver_id')
    def _compute_ownership_driver_id(self):
        for partner in self:
            emp = partner.employee_link_ids[:1]
            partner.ownership_driver_id = emp.ownership_driver_id.id if emp and emp.ownership_driver_id else False

    @api.depends('license_expiry')
    def _compute_license_expiry(self):
        today = date.today()
        for driver in self:
            driver.is_license_expiring = driver.license_expiry and (driver.license_expiry - today).days <= 30

    # @api.depends('id')
    # def compute_diciplinary_count(self):
    #     for record in self:
    #         record.diciplinary_count = len(record.emp_violation_ids)

    def compute_diciplinary_count(self):
        for record in self:
            diciplinary_total = len(record.emp_violation_ids)
            record.diciplinary_count = diciplinary_total

    # @api.depends('emp_violation_ids')
    # def _compute_diciplinary_count(self):
    #     for partner in self:
    #         partner.diciplinary_count = len(partner.emp_violation_ids)

    def action_view_diciplinaries(self):
        employee = self.env['hr.employee'].search([
            ('partner_id', '=', self.id)
        ], limit=1)
        return {
            'name': 'Disciplinary Records',
            'type': 'ir.actions.act_window',
            'res_model': 'disicplinary.line',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_employee_id': employee.id,
            },
        }

    @api.onchange('availability')
    def update_vehicle_last_status(self):
        for rec in self:
            if rec and rec.vehicle_id and rec.availability in ["Sakit", "Cuti", "Absent"]:
                rec.vehicle_id.vehicle_status = "not_ready"
                status = self.env['fleet.vehicle.status'].search([('name_description', 'ilike', 'driver not')], limit=1)
                if status:
                    rec.vehicle_id.last_status_description_id = status.id

            if rec.vehicle_id:
                if rec.availability == 'Ready':
                    rec.vehicle_id.driver_confirmation = True
                else:
                    rec.vehicle_id.driver_confirmation = False

    # def action_view_employees(self):
    #     self.ensure_one()
    #     return {
    #         'name': 'Employees',
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'hr.employee',
    #         'view_mode': 'tree,form',
    #         'domain': [('res_partner_id', '=', self.id)],
    #         'context': {'res_partner_id': self.id},
    #     }
    #
    # @api.depends('id')
    # def _compute_diciplinary_count(self):
    #     for partner in self:
    #         partner.employee_count = self.env['hr.employee'].search_count([
    #             ('address_home_id', '=', partner.id)
    #         ])

    @api.constrains('header_bop')
    def _check_unique_header_bop(self):
        for rec in self:
            if rec.header_bop:
                domain = [('header_bop', '=', True)]
                if rec.id and isinstance(rec.id, int):
                    domain.append(('id', '!=', rec.id))
                existing = self.env['res.partner'].search(domain, limit=1)
                if existing:
                    raise ValidationError("Only one partner can have 'Header Bop' checked.")

    def write(self, vals):
        for record in self:
            if vals.get('header_bop'):
                self.env['res.partner'].search([
                    ('header_bop', '=', True),
                    ('id', '!=', record.id)
                ]).write({'header_bop': False})
        return super().write(vals)

    @api.onchange('header_bop')
    def _onchange_header_bop(self):
        if self.header_bop:
            domain = [('header_bop', '=', True)]
            if self.id and isinstance(self.id, int):
                domain.append(('id', '!=', self.id))
            existing = self.env['res.partner'].search(domain, limit=1)
            if existing:
                self.header_bop = False
                return {
                    'warning': {
                        'title': "Warning",
                        'message': (
                            f"Only one partner can have 'Header Bop' checked.\n\n"
                            f"Currently checked on: {existing.name}.\n"
                            f"Please uncheck that contact first."
                        ),
                    }
                }

    # @api.model
    # def _check_unique_header_bop(self):
    #     for rec in self:
    #         if rec.header_bop:
    #             existing = self.env['res.partner'].search([
    #                 ('header_bop', '=', True),
    #                 ('id', '!=', rec.id)
    #             ], limit=1)
    #             if existing:
    #                 raise ValidationError(
    #                     "Only one contact can be checked as 'Header Bop'. "
    #                     "Please uncheck it from the other contact first."
    #                 )
