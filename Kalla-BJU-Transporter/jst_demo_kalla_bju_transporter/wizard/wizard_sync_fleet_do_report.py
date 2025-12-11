# models/wizard_sync_fleet_do_report.py
from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError


class SyncFleetDoReportWizard(models.TransientModel):
    _name = 'sync.fleet.do.report.wizard'
    _description = 'Wizard: Sync DO Report by Date Range'

    date_start  = fields.Date(string='Tanggal Mulai', required=True, default=lambda self: fields.Date.context_today(self))
    date_end    = fields.Date(string='Tanggal Berakhir', required=True, default=lambda self: fields.Date.context_today(self))
    fleet_do_id = fields.Many2one('fleet.do')

    def action_sync(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError(_("Tanggal berakhir tidak boleh lebih awal dari tanggal mulai."))

        # jalankan sinkronisasi
        self.env['fleet.do'].sync_do_report_for_range(self.date_start, self.date_end, self.fleet_do_id.id)

        # balik ke list DO Report (opsional: filter range)
        action = self.env.ref('jst_demo_kalla_bju_transporter.fleet_do_report_action').read()[0]
        action['domain'] = ['|',
            '&', ('tgl_masuk','>=', self.date_start), ('tgl_masuk','<=', self.date_end),
            '&', ('tgl_keluar','>=', self.date_start), ('tgl_keluar','<=', self.date_end),
        ]
        return action
    
