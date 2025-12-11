from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'portfolio.view.mixin']

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_do', "DO Line"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    fleet_do_id = fields.Many2one(
        'fleet.do',
        string='Fleet DO',
        ondelete='set null'
    )
    has_fleet_do = fields.Boolean(
        compute='_compute_has_fleet_do',
        string='Has Fleet DO'
    )
    fleet_do_count = fields.Integer(
        compute='_compute_fleet_do_count',
        string='Fleet DO Count'
    )

    @api.model
    def _generate_fleet_po_name(self, company_code=None):
        """
        Generate custom PO name berdasarkan company_code:
        - BONE, MKS, ARM → PO-CODE-YYYY-NNNNN
        - Selain itu (misalnya LMKS) → PO/NNNNN/CODE/MM/YYYY
        """
        if not company_code:
            raise UserError(_("Company Code belum diisi pada perusahaan."))

        # Ambil sequence khusus per company
        sequence_code = f"purchase.order.{company_code}"
        nomor_urut = self.env["ir.sequence"].next_by_code(sequence_code)

        if not nomor_urut:
            raise UserError(_("Sequence %s belum dibuat.") % sequence_code)

        bulan = datetime.today().month
        tahun = datetime.today().year

        # Kondisi khusus
        if company_code in ["BONE", "MKS", "ARM"]:
            return f"PO-{company_code}-{tahun}-{nomor_urut}"
        else:
            return f"PO/{nomor_urut}/{company_code}/{bulan}/{tahun}"

    @api.model
    def create(self, vals):
        if vals.get("name", "New") in ("New", "/"):
            company_id = None

            # Jika ada company_ids → ambil yang pertama
            if vals.get("company_ids"):
                # vals['company_ids'] format: [(6, 0, [id1, id2, ...])]
                company_ids = vals["company_ids"][0][2]
                if company_ids:
                    company_id = company_ids[0]

            # Kalau tidak ada company_ids → fallback ke company_id tunggal
            if not company_id:
                company_id = vals.get("company_id") or self.env.user.company_id.id

            company = self.env["res.company"].browse(company_id)
            company_code = company.company_code and company.company_code.strip() or False

            if not company_code:
                raise UserError(_("Company Code perusahaan kosong, silakan isi dulu di Settings."))

            if company_code and self.is_lms(self.env.company.portfolio_id.name):
                vals["name"] = self._generate_fleet_po_name(company_code)

        return super(PurchaseOrder, self).create(vals)

    @api.depends('fleet_do_id')
    def _compute_has_fleet_do(self):
        for record in self:
            record.has_fleet_do = bool(record.fleet_do_id)

    @api.depends('fleet_do_id')
    def _compute_fleet_do_count(self):
        for record in self:
            record.fleet_do_count = 1 if record.fleet_do_id else 0

    def action_view_fleet_do(self):
        """Action untuk smart button melihat Fleet DO"""
        self.ensure_one()
        if not self.fleet_do_id:
            # Jika belum ada fleet DO, buat yang baru
            return self.action_create_fleet_do()

        return {
            'name': 'Fleet Delivery Order',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.do',
            'view_mode': 'form',
            'res_id': self.fleet_do_id.id,
            'target': 'current',
            'context': {'create': False}
        }

    @api.constrains('fleet_do_id')
    def _check_unique_fleet_do(self):
        """Constraint untuk memastikan Fleet DO hanya terhubung ke satu PO"""
        for record in self:
            if record.fleet_do_id:
                existing = self.search([
                    ('fleet_do_id', '=', record.fleet_do_id.id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        f"Fleet DO {record.fleet_do_id.name} sudah terhubung dengan Purchase Order {existing.name}!"
                    )
                    
    def action_create_invoice(self):
        for order in self:
            if self.env.company.portfolio_id.name != 'Frozen':
                do = order.fleet_do_id
                if do and do.state != 'done':
                    raise UserError((
                        "Tidak bisa membuat Create Bill karena DO '%(do)s' belum selesai (done)"
                        "(status: %(st)s)."
                    ) % {
                        'do': do.display_name,
                        'st': do.state
                    })

        res = super().action_create_invoice()

        for order in self:
            if self.env.company.portfolio_id.name != 'Frozen':
                do = order.fleet_do_id
                if do:
                    order_ids = [line.order_id.id for line in do.po_line_ids]
                    orders = self.env['sale.order'].browse(order_ids)
                    print('order : ', orders)

                    no_surat_jalan_list = []
                    for so in orders:
                        no_surat_jalan_list += so.order_line._collect_no_surat_jalan()
                        filtered_order_line = so.order_line.filtered(lambda r: r.no_surat_jalan and r.do_id)
                        print('no_surat_jalan_list : ', no_surat_jalan_list)
                        for order_line in filtered_order_line:
                            filtered_order_line._update_related_records(order_line, no_surat_jalan_list)

        return res
    
    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.fleet_do_id and self.origin:
            vals['ref'] = self.origin
        return vals

    # class PurchaseOrderLine(models.Model):
    #     _name = 'purchase.order.line'
    #     _inherit = ['purchase.order.line', 'portfolio.view.mixin']

    #     def _prepare_account_move_line(self, move=False):
    #         res = super()._prepare_account_move_line(move=move)
    #         _logger.info(f'Preparing Bill Lines => {res}')
    #         # Ini adalah proses untuk mengosongkan dulu account_id "Prepaid Expense"
    #         if 'account_id' not in res:
    #             res['account_id'] = None
    #         return res