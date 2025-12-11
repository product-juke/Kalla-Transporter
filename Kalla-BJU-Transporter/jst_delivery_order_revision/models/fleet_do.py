from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_round


class FleetDo(models.Model):
    _inherit = 'fleet.do'

    bop_driver_used = fields.Float('BOP Driver yang digunakan')

    @api.depends('po_line_ids', 'po_line_ids.is_header', 'vehicle_id', 'vehicle_id.asset_type', 'bop_driver_used')
    def compute_nominal(self):
        res = super().compute_nominal()
        for rec in self:
            for line in rec.po_line_ids:
                if line.is_header_from_revision and line.prev_bop > 0:
                    rec.nominal = line.prev_bop
                    break

            if rec.bop_driver_used > 0:
                # Adjust nominal jika ada BOP yang digunakan
                rec.nominal = rec.nominal - rec.bop_driver_used

        return res

    def action_revisi_do(self):
        """Open wizard for DO revision"""
        if not self.po_line_ids:
            raise UserError("Tidak ada PO Lines yang tersedia untuk direvisi.")

        return {
            'name': 'Revisi DO',
            'type': 'ir.actions.act_window',
            'res_model': 'do.revision.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_do_id': self.id,
                # 'default_po_line_ids': [(6, 0, self.po_line_ids.ids)],
                'default_po_line_ids': [],
            }
        }

    def action_use_remaining_bop(self):
        """Action untuk menggunakan saldo BOP Driver"""
        self.ensure_one()

        # Ambil semua saldo BOP Driver yang tersedia (remaining_bop > 0)
        bop_balances = self.env['driver.bop.balance'].search([
            ('driver_id', '=', self.driver_id.id),
            ('remaining_bop', '>', 0)
        ])

        if not bop_balances:
            raise UserError('Tidak ada saldo BOP Driver yang tersedia.')

        # Hitung total saldo BOP yang tersedia
        total_bop_remaining = sum(bop_balances.mapped('remaining_bop'))

        # Tentukan nilai default untuk penggunaan BOP
        nominal = self.nominal or 0.0
        default_bop_usage = min(total_bop_remaining, nominal)

        # Buat wizard
        wizard = self.env['fleet.do.use.bop.wizard'].create({
            'fleet_do_id': self.id,
            'current_nominal': nominal,
            'bop_amount': default_bop_usage,
        })

        # Buat wizard lines untuk setiap BOP balance
        for bop_balance in bop_balances:
            self.env['fleet.do.use.bop.wizard.line'].create({
                'wizard_id': wizard.id,
                'bop_balance_id': bop_balance.id,
                'selected': True,  # Default semua terpilih
            })

        return {
            'name': 'Gunakan Saldo BOP Driver',
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.do.use.bop.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
