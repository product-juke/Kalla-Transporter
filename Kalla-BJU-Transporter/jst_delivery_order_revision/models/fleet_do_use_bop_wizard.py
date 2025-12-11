from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FleetDoUseBopWizard(models.TransientModel):
    _name = 'fleet.do.use.bop.wizard'
    _description = 'Wizard untuk Menggunakan Saldo BOP Driver'

    fleet_do_id = fields.Many2one('fleet.do', string='Delivery Order', required=True)
    driver_id = fields.Many2one('res.partner', string='Driver', related='fleet_do_id.driver_id', readonly=True)
    bop_balance_line_ids = fields.One2many(
        'fleet.do.use.bop.wizard.line',
        'wizard_id',
        string='Saldo BOP Driver'
    )
    driver_bop_remaining = fields.Monetary(
        string='Total Saldo BOP Terpilih',
        compute='_compute_driver_bop_remaining',
        currency_field='currency_id'
    )
    current_nominal = fields.Monetary(
        string='Nominal Saat Ini',
        readonly=True,
        currency_field='currency_id'
    )
    bop_amount = fields.Monetary(
        string='Jumlah BOP yang Digunakan',
        required=True,
        currency_field='currency_id',
        default=0.0
    )
    new_nominal = fields.Monetary(
        string='Nominal Setelah Pengurangan',
        compute='_compute_new_nominal',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    info_message = fields.Html(
        string='Informasi',
        compute='_compute_info_message'
    )

    @api.depends('bop_balance_line_ids', 'bop_balance_line_ids.selected', 'bop_balance_line_ids.remaining_bop')
    def _compute_driver_bop_remaining(self):
        for record in self:
            total = sum(
                line.remaining_bop
                for line in record.bop_balance_line_ids
                if line.selected
            )
            record.driver_bop_remaining = total

    @api.depends('current_nominal', 'bop_amount')
    def _compute_new_nominal(self):
        for record in self:
            record.new_nominal = record.current_nominal - record.bop_amount

    @api.depends('bop_amount', 'new_nominal')
    def _compute_info_message(self):
        for record in self:
            record.info_message = f"""
                <div class="alert alert-info" role="alert">
                    <strong>Informasi:</strong><br/>
                    Ketika Anda submit, field <strong>Nominal</strong> pada Delivery Order 
                    akan berubah dari <strong>{self.env.company.currency_id.symbol} 
                    {record.current_nominal:,.2f}</strong> menjadi <strong>
                    {self.env.company.currency_id.symbol} {record.new_nominal:,.2f}</strong>
                    <br/><br/>
                    Saldo BOP Driver akan berkurang sebesar <strong>
                    {self.env.company.currency_id.symbol} {record.bop_amount:,.2f}</strong>
                </div>
            """

    @api.onchange('bop_balance_line_ids', 'bop_balance_line_ids.selected')
    def _onchange_bop_balance_lines(self):
        """Update default bop_amount when selection changes"""
        # Force recompute driver_bop_remaining
        self._compute_driver_bop_remaining()

        if self.driver_bop_remaining > 0:
            if self.driver_bop_remaining >= self.current_nominal:
                self.bop_amount = self.current_nominal
            else:
                self.bop_amount = self.driver_bop_remaining

    @api.constrains('bop_amount')
    def _check_bop_amount(self):
        # Skip constraint saat wizard baru dibuat
        if self.env.context.get('skip_bop_constraint'):
            return

        for record in self:
            if record.bop_amount <= 0:
                raise ValidationError('Jumlah BOP yang digunakan harus lebih besar dari 0.')

            if record.bop_amount > record.driver_bop_remaining:
                raise ValidationError(
                    f'Jumlah BOP yang digunakan ({record.bop_amount:,.2f}) '
                    f'tidak boleh melebihi total saldo BOP Driver yang terpilih '
                    f'({record.driver_bop_remaining:,.2f}).'
                )

            if record.bop_amount > record.current_nominal:
                raise ValidationError(
                    f'Jumlah BOP yang digunakan ({record.bop_amount:,.2f}) '
                    f'tidak boleh melebihi nominal saat ini ({record.current_nominal:,.2f}).'
                )

    def action_confirm(self):
        """Konfirmasi penggunaan BOP Driver"""
        self.ensure_one()

        # Validasi ada BOP yang dipilih
        selected_lines = self.bop_balance_line_ids.filtered(lambda l: l.selected)
        if not selected_lines:
            raise ValidationError('Pilih minimal satu saldo BOP Driver untuk digunakan.')

        # Update nominal pada fleet.do
        self.fleet_do_id.write({
            'prev_nominal': self.fleet_do_id.nominal,
        })
        self.fleet_do_id.with_context(new_nominal=self.new_nominal).write({
            'nominal': self.new_nominal,
            'bop_driver_used': self.bop_amount,
        })

        # Update saldo BOP Driver per line yang dipilih
        remaining_amount = self.bop_amount

        for line in selected_lines.sorted(key=lambda l: l.bop_balance_id.id):
            if remaining_amount <= 0:
                break

            bop_balance = line.bop_balance_id
            amount_to_use = min(remaining_amount, bop_balance.remaining_bop)

            self.env['driver.bop.balance.history'].create({
                'bop_balance_id': bop_balance.id,
                'driver_id': self.driver_id.id,
                'do_id': self.fleet_do_id.id,
                'initial_bop_value': bop_balance.remaining_bop,
                'used_bop': amount_to_use,
            })

            # Update driver.bop.balance
            bop_balance.write({
                'used_bop': bop_balance.used_bop + amount_to_use,
                'remaining_bop': bop_balance.remaining_bop - amount_to_use,
            })

            remaining_amount -= amount_to_use

            # Buat log jika diperlukan
            self._create_bop_usage_log(bop_balance, amount_to_use)

        return {'type': 'ir.actions.act_window_close'}

    def _create_bop_usage_log(self, bop_balance, amount_used):
        """Opsional: Buat log penggunaan BOP"""
        # Implementasi jika Anda ingin membuat history/log
        # Contoh: Tambahkan ke description
        if bop_balance.description:
            bop_balance.description += f"\n- Digunakan {amount_used:,.2f} untuk DO {self.fleet_do_id.name}"
        else:
            bop_balance.description = f"- Digunakan {amount_used:,.2f} untuk DO {self.fleet_do_id.name}"


class FleetDoUseBopWizardLine(models.TransientModel):
    _name = 'fleet.do.use.bop.wizard.line'
    _description = 'Wizard Line untuk Saldo BOP Driver'

    wizard_id = fields.Many2one('fleet.do.use.bop.wizard', string='Wizard', required=True, ondelete='cascade')
    bop_balance_id = fields.Many2one('driver.bop.balance', string='BOP Balance', required=True)
    do_id = fields.Many2one('fleet.do', related='bop_balance_id.do_id', string='DO Asal', readonly=True)
    total_bop = fields.Float('Total BOP', related='bop_balance_id.total_bop', readonly=True)
    used_bop = fields.Float('Terpakai', related='bop_balance_id.used_bop', readonly=True)
    remaining_bop = fields.Float('Sisa', related='bop_balance_id.remaining_bop', readonly=True)
    description = fields.Text('Keterangan', related='bop_balance_id.description', readonly=True)
    selected = fields.Boolean('Pilih', default=False)