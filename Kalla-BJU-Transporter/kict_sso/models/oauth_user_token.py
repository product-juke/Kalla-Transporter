from odoo import models, fields, api
from datetime import datetime, timedelta
import requests


class KICTOAuthUserToken(models.Model):
    _name = 'kict.oauth.user.token'
    _description = 'KICT OAuth User Token'

    user_id = fields.Many2one(
        'res.users', 'User', required=True, ondelete='cascade')
    provider_id = fields.Many2one(
        'kict.oauth2.provider', 'OAuth Provider', required=True)
    username = fields.Char('OAuth Username')
    access_token = fields.Text('Access Token', required=True)
    refresh_token = fields.Text('Refresh Token')
    token_expires = fields.Datetime('Token Expires')

    access_token_masked = fields.Char(
        'Access Token (Masked)', compute='_compute_masked_tokens')
    refresh_token_masked = fields.Char(
        'Refresh Token (Masked)', compute='_compute_masked_tokens')

    @api.depends('access_token', 'refresh_token')
    def _compute_masked_tokens(self):
        for record in self:
            record.access_token_masked = self._mask_token(record.access_token)
            record.refresh_token_masked = self._mask_token(
                record.refresh_token)

    def _mask_token(self, token):
        if not token:
            return ''
        if len(token) <= 8:
            return '*' * len(token)
        return token[:4] + '*' * (len(token) - 8) + token[-4:]

    _sql_constraints = [
        ('unique_user_provider', 'unique(user_id, provider_id)',
         'User can have only one token per provider')
    ]

    def refresh_oauth_token(self):
        """Refresh OAuth token"""
        if not self.refresh_token:
            return False

        token_data = {
            'grant_type': 'refresh_token',
            'client_id': self.provider_id.client_id,
            'client_secret': self.provider_id.client_secret,
            'refresh_token': self.refresh_token,
        }

        try:
            response = requests.post(
                self.provider_id.token_url, data=token_data)
            if response.status_code == 200:
                token_info = response.json()
                expires_in = token_info.get('expires_in', 3600)

                self.write({
                    'access_token': token_info.get('access_token'),
                    'refresh_token': token_info.get('refresh_token', self.refresh_token),
                    'token_expires': datetime.now() + timedelta(seconds=expires_in),
                })
                return True
        except Exception:
            pass
        return False
