from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BopAdditionalCostWizard(models.TransientModel):
    _name = 'bop.additional.cost.wizard'
    _description = 'Penambahan Biaya Tambahan BOP'

    fleet_do_id = fields.Many2one('fleet.do', string="DO Reference")
    amount_paid = fields.Monetary('Amount Paid', currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)
    product_ids = fields.Many2many(
        'product.product',
        'bop_addcost_product_rel', 'wizard_id', 'product_id',
        string='Produk Biaya Tambahan',
        domain="[('categ_id.name', 'ilike', 'Biaya Tambahan')]"
    )
    attachment = fields.Binary(string='Lampiran', attachment=True)
    attachment_filename = fields.Char(string='Nama File')

    def action_bop_additional_cost(self):
        self.ensure_one()
        do = self.fleet_do_id
        if not do:
            raise UserError(_("Tidak ada Delivery Order yang dipilih."))

        tier_definition = self.env['tier.definition'].search([
            ('reviewer_id', '=', self.env.user.id),
            ('review_state', '=', 'approved_cashier'),
            ('model', '=', 'bop.line'),
        ], limit=1)
        if not tier_definition:
            raise UserError(_("Anda tidak memiliki akses untuk menambahkan biaya tambahan BOP"))

        # Ambil label branch project utk nomor BOP
        bp_codes = do.po_line_ids.order_id.mapped('branch_project')
        code = bp_codes[0] if bp_codes else False
        selection = dict(self.env['sale.order']._fields['branch_project'].selection)
        bp_label = selection.get(code, code)

        # Generate nomor BOP
        bop_no = self.env['bop.line'].generate_fleet_bop_name(bp_label)

        bop_vals = {
            'fleet_do_id': do.id,
            'is_created_form': 'BOP',
            'amount_paid': self.amount_paid,
            'is_additional_cost': True,
            'is_settlement': False,
            'paid_status': 'not_paid',
            'bop_no': bop_no,
            'state': 'draft',
            'product_ids': [(6, 0, self.product_ids.ids)],

            # ⬇️ simpan file langsung di bop.line
            'attachment': self.attachment,
            'attachment_filename': self.attachment_filename or f"lampiran_bop_{bop_no}",
        }
        bop = self.env['bop.line'].create(bop_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('BOP'),
            'res_model': 'bop.line',
            'view_mode': 'form',
            'res_id': bop.id,
            'target': 'current',
        }
        