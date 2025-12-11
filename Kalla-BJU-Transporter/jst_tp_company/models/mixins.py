from odoo import models, fields, api

class PortfolioViewMixin(models.AbstractModel):
    _name = 'portfolio.view.mixin'
    _description = 'Base Mixin for Portfolio-based Field Visibility'

    show_field = fields.Char(compute='_compute_show_field', store=False)

    @api.onchange('company_id')
    def _onchange_show_field(self):
        self._compute_show_field()

    def _target_portfolio(self):
        return None

    def _compute_show_field(self):
        for rec in self:
            rec.show_field = rec.env.company.portfolio_id.name

    def is_vli(self, current_portfolio = ""):
        return current_portfolio and str(current_portfolio).lower() in ['vli']

    def is_lms(self, current_portfolio = ""):
        return current_portfolio and str(current_portfolio).lower() in ['transporter', 'vli', 'trucking']

    def is_fms(self, current_portfolio = ""):
        return current_portfolio and str(current_portfolio).lower() == 'frozen'


class TransporterViewMixin(models.AbstractModel):
    _name = 'transporter.view.mixin'
    _inherit = 'portfolio.view.mixin'
    _description = 'Field visibility for Transporter'

    def _target_portfolio(self):
        return 'Transporter'

class TruckingViewMixin(models.AbstractModel):
    _name = 'trucking.view.mixin'
    _inherit = 'portfolio.view.mixin'
    _description = 'Field visibility for Trucking'

    def _target_portfolio(self):
        return 'trucking'

class FrozenViewMixin(models.AbstractModel):
    _name = 'frozen.view.mixin'
    _inherit = 'portfolio.view.mixin'
    _description = 'Field visibility for Frozen'

    def _target_portfolio(self):
        return 'Frozen'
