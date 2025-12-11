from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class DriverBOPBalance(models.Model):
    _name = 'driver.bop.balance'

    driver_id = fields.Many2one('res.partner', tracking=True)
    do_id = fields.Many2one('fleet.do', tracking=True)
    total_bop = fields.Float('Total BOP', tracking=True)
    used_bop = fields.Float('Terpakai (Rp.)', tracking=True)
    remaining_bop = fields.Float('Sisa (Rp.)', tracking=True)
    description = fields.Text('Keterangan', tracking=True, default='-')

    # New fields untuk rincian BOP
    bop_usage_detail_ids = fields.One2many(
        'driver.bop.usage.detail',
        'bop_balance_id',
        string='Rincian Penggunaan BOP'
    )
    remaining_bop_detail_ids = fields.One2many(
        'driver.bop.remaining.detail',
        'bop_balance_id',
        string='Rincian Sisa BOP'
    )

    bop_balance_history_ids = fields.One2many(
        'driver.bop.balance.history',
        'bop_balance_id',
        string='History BOP Driver'
    )

    created_date_label = fields.Char(
        string='Tanggal Dibuat',
        compute='_compute_created_date_label',
        store=False
    )

    @api.depends('create_date')
    def _compute_created_date_label(self):
        for record in self:
            if record.create_date:
                create_date_local = fields.Datetime.context_timestamp(record, record.create_date)
                bulan = [
                    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
                ]
                record.created_date_label = create_date_local.strftime(
                    f'%d {bulan[create_date_local.month - 1]} %Y, %H:%M')
            else:
                record.created_date_label = ''

    def action_return_bop(self):
        self.ensure_one()

        if self.remaining_bop <= 0:
            raise UserError(_('Tidak ada sisa BOP yang dapat dikembalikan.'))

        return {
            'name': _('Kembalikan BOP'),
            'type': 'ir.actions.act_window',
            'res_model': 'driver.bop.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bop_balance_id': self.id,
                'default_return_amount': self.remaining_bop,
            }
        }


class DriverBOPUsageDetail(models.Model):
    _name = 'driver.bop.usage.detail'
    _description = 'Detail Penggunaan BOP Driver'

    bop_balance_id = fields.Many2one('driver.bop.balance', string='BOP Balance', required=True, ondelete='cascade')
    description = fields.Char(string='Keterangan', required=True)
    amount = fields.Float(string='Jumlah', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'driver_bop_usage_detail_attachment_rel',
        'detail_id',
        'attachment_id',
        string='Lampiran'
    )


class DriverBOPRemainingDetail(models.Model):
    _name = 'driver.bop.remaining.detail'
    _description = 'Detail Sisa BOP Driver'

    bop_balance_id = fields.Many2one('driver.bop.balance', string='BOP Balance', required=True, ondelete='cascade')
    description = fields.Char(string='Keterangan Sisa BOP', required=True)
    amount = fields.Float(string='Jumlah', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'driver_bop_remaining_detail_attachment_rel',
        'detail_id',
        'attachment_id',
        string='Lampiran'
    )


class DriverBOPBalanceHistory(models.Model):
    _name = 'driver.bop.balance.history'

    bop_balance_id = fields.Many2one('driver.bop.balance', string='BOP Balance', required=True)
    driver_id = fields.Many2one('res.partner', tracking=True)
    do_id = fields.Many2one('fleet.do', tracking=True)
    initial_bop_value = fields.Float('Nilai Awal BOP', tracking=True)
    used_bop = fields.Float('Terpakai (Rp.)', tracking=True)
    description = fields.Text('Keterangan', tracking=True, default='-')


class DriverBOPReturnWizard(models.TransientModel):
    _name = 'driver.bop.return.wizard'
    _description = 'Wizard untuk Pengembalian BOP Driver'

    bop_balance_id = fields.Many2one('driver.bop.balance', string='BOP Balance', required=True)
    return_amount = fields.Float('Jumlah BOP Dikembalikan', required=True, readonly=True)
    account_id = fields.Many2one(
        'account.account',
        string='Akun Kredit',
        required=True,
        help='Pilih akun yang akan di-kredit untuk pengembalian BOP'
    )
    description = fields.Text('Keterangan', default='Pengembalian BOP Driver')

    @api.constrains('return_amount')
    def _check_return_amount(self):
        for wizard in self:
            if wizard.return_amount <= 0:
                raise ValidationError(_('Jumlah pengembalian harus lebih besar dari 0.'))

    def action_confirm_return(self):
        self.ensure_one()

        bop_balance = self.bop_balance_id

        if self.return_amount > bop_balance.remaining_bop:
            raise UserError(_('Jumlah pengembalian tidak boleh melebihi sisa BOP.'))

        debit_account = self.env['account.account'].search([
            ('is_for_driver_remaining_bop', '=', True)
        ], limit=1)

        if not debit_account:
            raise UserError(_('Akun untuk Sisa BOP Driver tidak ditemukan. Pastikan ada akun dengan flag "is_for_driver_remaining_bop" = True.'))

        journal = self.env['account.journal'].search([
            ('type', '=', 'general')
        ], limit=1)

        if not journal:
            raise UserError(_('Journal MISC tidak ditemukan.'))

        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'ref': f'Pengembalian BOP - {bop_balance.driver_id.name or ""} - DO: {bop_balance.do_id.name or ""}',
            'line_ids': [
                (0, 0, {
                    'account_id': debit_account.id,
                    'name': self.description or 'Pengembalian BOP Driver',
                    'debit': self.return_amount,
                    'credit': 0.0,
                    'analytic_distribution': self.env['account.move']._create_analytic_distribution(bop_balance)
                }),
                (0, 0, {
                    'account_id': self.account_id.id,
                    'name': self.description or 'Pengembalian BOP Driver',
                    'debit': 0.0,
                    'credit': self.return_amount,
                    'analytic_distribution': self.env['account.move']._create_analytic_distribution(bop_balance)
                }),
            ]
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        bop_balance.write({
            'used_bop': bop_balance.used_bop + self.return_amount,
            'remaining_bop': 0.0,
        })

        self.env['driver.bop.balance.history'].create({
            'bop_balance_id': bop_balance.id,
            'driver_id': bop_balance.driver_id.id,
            'do_id': bop_balance.do_id.id,
            'initial_bop_value': bop_balance.remaining_bop + self.return_amount,
            'used_bop': self.return_amount,
            'description': f'{self.description}\nJournal Entry: {move.name}',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Berhasil'),
                'message': _('BOP berhasil dikembalikan dan Journal Entry telah dibuat.'),
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                },
            }
        }