from odoo import models, fields, api


class DisciplinaryStatus(models.Model):
    _name = 'disciplinary.status'
    _description = 'Disciplinary Status Master Data'
    _order = 'name'

    name = fields.Char(
        string='Status Name',
        required=True,
        help='Nama status pelanggaran (contoh: SP1, SP2, Teguran Lisan)'
    )

    description = fields.Text(
        string='Description',
        help='Deskripsi detail tentang status pelanggaran'
    )

    severity_level = fields.Selection([
        ('1', 'Level 1 - Ringan'),
        ('2', 'Level 2 - Sedang'),
        ('3', 'Level 3 - Berat'),
        ('4', 'Level 4 - Sangat Berat'),
        ('5', 'Level 5 - Pemutusan Hubungan Kerja')
    ], string='Severity Level', required=True, default='1')

    action_required = fields.Text(
        string='Action Required',
        help='Tindakan yang harus dilakukan untuk status ini'
    )

    duration_days = fields.Integer(
        string='Duration (Days)',
        help='Lama berlaku status dalam hari (jika applicable)'
    )

    is_final = fields.Boolean(
        string='Is Final Status',
        default=False,
        help='Centang jika ini adalah status terakhir (seperti PHK)'
    )

    next_status_id = fields.Many2one(
        'disciplinary.status',
        string='Next Status',
        help='Status berikutnya jika pelanggaran berulang'
    )

    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Warna untuk tampilan kanban'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Relasi untuk melihat penggunaan
    disciplinary_line_ids = fields.One2many(
        'disicplinary.line',
        'status_id',
        string='Disciplinary Lines'
    )

    disciplinary_count = fields.Integer(
        string='Disciplinary Count',
        compute='_compute_disciplinary_count'
    )

    @api.depends('disciplinary_line_ids')
    def _compute_disciplinary_count(self):
        for record in self:
            record.disciplinary_count = len(record.disciplinary_line_ids)

    def action_view_disciplinary_lines(self):
        """Action untuk melihat disciplinary lines yang menggunakan status ini"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disciplinary Lines - {self.name}',
            'res_model': 'disicplinary.line',
            'view_mode': 'tree,form',
            'domain': [('status_id', '=', self.id)],
            'context': {'default_status_id': self.id}
        }