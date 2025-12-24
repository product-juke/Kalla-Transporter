from odoo import models, fields
from datetime import datetime


class ResUsers(models.Model):
    _inherit = 'res.users'

    oauth_token_ids = fields.One2many(
        'kict.oauth.user.token', 'user_id', 'OAuth Tokens')

    def get_oauth_token(self, provider_id, auto_refresh=True):
        """Get OAuth token for specific provider with auto refresh"""
        token = self.oauth_token_ids.filtered(
            lambda t: t.provider_id.id == provider_id)
        if not token:
            return None

        token = token[0]

        # Auto refresh if token expired and auto_refresh enabled
        if auto_refresh and token.token_expires and token.token_expires <= datetime.now():
            if token.refresh_oauth_token():
                token = token  # Refresh successful
            else:
                return None  # Refresh failed

        return token
