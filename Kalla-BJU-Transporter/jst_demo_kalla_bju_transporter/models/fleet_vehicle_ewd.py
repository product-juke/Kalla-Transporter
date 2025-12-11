from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date
import calendar

class FleetVehicleEwd(models.Model):
    _name = 'fleet.vehicle.ewd'
    _description = 'Effective Working Days (EWD)'

    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string="Vehicle",
        required=True
    )

    ewd_year = fields.Integer(
        string='Tahun',
        default=lambda self: fields.Date.today().year,
        help="Tahun perhitungan EWD."
    )
    ewd_month = fields.Selection(
        selection=[
            ('1', 'Januari'), ('2', 'Februari'), ('3', 'Maret'),
            ('4', 'April'), ('5', 'Mei'), ('6', 'Juni'),
            ('7', 'Juli'), ('8', 'Agustus'), ('9', 'September'),
            ('10', 'Oktober'), ('11', 'November'), ('12', 'Desember')
        ],
        string='Bulan',
        default=lambda self: str(fields.Date.today().month),
        help="Bulan perhitungan EWD."
    )
    ewd_total_days = fields.Integer(
        string='Total Hari',
        compute='_compute_ewd_fields',
        store=True,
        help="Total hari dalam bulan yang dipilih (ikut tahun untuk leap year)."
    )
    ewd_total_weekend = fields.Integer(
        string='Total Weekend (Hari Minggu)',
        compute='_compute_ewd_fields',
        store=True,
        help="Jumlah hari Minggu pada bulan & tahun yang dipilih."
    )
    ewd_total_holidays = fields.Integer(
        string='Total Hari Libur (Nasional)',
        default=0,
        help="Jumlah hari libur di luar hari Minggu pada bulan tsb (input manual)."
    )
    ewd_effective_working_days = fields.Integer(
        string='EWD',
        compute='_compute_ewd_fields',
        store=True,
        help="Effective Working Days = Total Hari - total Weekend (Hari Minggu) -  Total Hari Libur (Nasional)."
    )

    @api.depends('ewd_year', 'ewd_month', 'ewd_total_holidays')
    def _compute_ewd_fields(self):
        for rec in self:
            # fallback aman
            year = rec.ewd_year or fields.Date.today().year
            month = int(rec.ewd_month or fields.Date.today().month)

            # Total hari dalam bulan (perhatikan leap year)
            _, days_in_month = calendar.monthrange(year, month)
            total_days = days_in_month

            # Hitung jumlah Minggu (weekday(): Mon=0 ... Sun=6)
            total_sundays = sum(
                1 for d in range(1, days_in_month + 1)
                if date(year, month, d).weekday() == 6
            )

            # Hari libur manual (pastikan tidak negatif & tidak melebihi total hari)
            holidays = rec.ewd_total_holidays if rec.ewd_total_holidays is not None else 0
            holidays = max(0, holidays)  # cegah negatif
            if holidays > total_days:
                # batasi agar tidak lebih dari total hari (jaga konsistensi tampilan)
                holidays = total_days

            rec.ewd_total_days = total_days
            rec.ewd_total_weekend = total_sundays
            rec.ewd_effective_working_days = total_days - total_sundays - holidays

    @api.onchange('ewd_year', 'ewd_month', 'ewd_total_holidays')
    def _onchange_ewd_preview(self):
        # Tidak perlu assign apa-apa; onchange ini hanya memicu recompute di UI.
        # Dibiarkan kosong supaya nilai compute langsung kelihatan saat user ganti input.
        pass

    @api.constrains('ewd_year')
    def _check_ewd_year(self):
        for rec in self:
            if rec.ewd_year and not (1970 <= rec.ewd_year <= 2100):
                raise ValidationError(_("Tahun harus antara 1970 hingga 2100."))

    @api.constrains('ewd_total_holidays', 'ewd_total_days')
    def _check_ewd_holidays(self):
        for rec in self:
            if rec.ewd_total_holidays is None:
                continue
            if rec.ewd_total_holidays < 0:
                raise ValidationError(_("Total hari libur tidak boleh negatif."))
            # saat create, ewd_total_days mungkin 0 dulu → toleransi
            if rec.ewd_total_days and rec.ewd_total_holidays > rec.ewd_total_days:
                raise ValidationError(_("Total hari libur tidak boleh melebihi total hari dalam bulan."))
            