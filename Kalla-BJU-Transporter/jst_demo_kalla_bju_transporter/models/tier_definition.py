from odoo import fields, api, models, _


class TierDefinition(models.Model):
    _inherit = "tier.definition"

    @api.model
    def _get_tier_validation_model_names(self):
        res = super(TierDefinition, self)._get_tier_validation_model_names()
        res += ["sale.order","account.move","fleet.do","bop.line"]
        return res
