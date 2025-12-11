from odoo import models, fields, api


class DisciplinaryActionPlan(models.Model):
    _name = 'disciplinary.action.plan'
    _description = 'Disciplinary Action Plan Master Data'
    _order = 'name'

    name = fields.Char(
        string='Action Plan',
        required=True,
        help='Nama rencana tindakan disipliner'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Relasi untuk melihat penggunaan (opsional)
    disciplinary_line_ids = fields.One2many(
        'disicplinary.line',
        'action_plan_id',
        string='Disciplinary Lines'
    )

    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count'
    )

    @api.depends('disciplinary_line_ids')
    def _compute_usage_count(self):
        for record in self:
            record.usage_count = len(record.disciplinary_line_ids)

    def action_view_disciplinary_lines(self):
        """Action untuk melihat disciplinary lines yang menggunakan action plan ini"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Disciplinary Lines - {self.name}',
            'res_model': 'disicplinary.line',
            'view_mode': 'tree,form',
            'domain': [('action_plan_id', '=', self.id)],
            'context': {'default_action_plan_id': self.id}
        }