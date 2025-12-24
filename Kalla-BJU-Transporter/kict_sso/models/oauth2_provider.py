from odoo import models, fields, api
import secrets
import string


class KICTOAuth2Provider(models.Model):
    _name = 'kict.oauth2.provider'
    _description = 'KICT OAuth2 Provider Configuration'

    name = fields.Char('Provider Name', required=True)
    client_id = fields.Char('Client ID', required=True)
    client_secret = fields.Char('Client Secret', required=True)
    authorization_url = fields.Char('Authorization URL', required=True)
    token_url = fields.Char('Token URL', required=True)
    userinfo_url = fields.Char('User Info URL', required=True)
    scope = fields.Char('Scope', default='openid profile email')
    icon_class = fields.Char(
        'Icon CSS Class',
        default='fa fa-fw fa-key',
        help='CSS class for the provider icon. Examples:\n'
             '• Kalla: "fa fa-fw o_oauth_kalla" (uses custom SVG)\n'
             '• FontAwesome: "fa fa-fw fa-[icon-name]" (e.g., fa-google, fa-microsoft)\n'
             '• Any valid FontAwesome icon class'
    )
    active = fields.Boolean('Active', default=True)
    redirect_uri = fields.Char(
        'Redirect URI',
    )

    @api.model
    def generate_client_secret(self):
        """Generate secure client secret"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))

    @api.model
    def create(self, vals):
        if not vals.get('client_secret'):
            vals['client_secret'] = self.generate_client_secret()
        return super().create(vals)
