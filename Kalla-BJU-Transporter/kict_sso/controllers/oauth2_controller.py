import requests
import urllib.parse
from odoo import http
from odoo.http import request
from werkzeug.utils import redirect
import logging

_logger = logging.getLogger(__name__)


class OAuth2Controller(http.Controller):

    @http.route(['/auth/oauth2/authorize', '/oauth/authorize'], type='http', auth='public', methods=['GET'])
    def oauth2_authorize(self, **kwargs):
        """Redirect to OAuth2 authorization server"""
        try:
            # Jika ada code, ini adalah callback dari Laravel
            if 'code' in kwargs:
                return self.oauth2_callback(**kwargs)

            # Request awal dari tombol login
            provider_id = kwargs.get('provider_id')
            if not provider_id:
                return "Error: Provider not specified"

            provider = request.env['kict.oauth2.provider'].sudo().browse(
                int(provider_id))
            if not provider.exists():
                return "Error: Provider not found"

            params = {
                'client_id': provider.client_id,
                'redirect_uri': provider.redirect_uri or (request.httprequest.url_root + 'oauth/callback'),
                'response_type': 'code',
                'scope': provider.scope,
                'state': provider_id,
            }

            auth_url = f"{provider.authorization_url}?{urllib.parse.urlencode(params)}"
            return f'<script>window.location.href="{auth_url}";</script>'
        except Exception as e:
            _logger.error(f"OAuth2 authorize error: {e}")
            return f"Error: {str(e)}"

    @http.route(['/auth/oauth2/callback', '/oauth/callback'], type='http', auth='public', methods=['GET'])
    def oauth2_callback(self, **kwargs):
        """Handle OAuth2 callback"""
        try:
            code = kwargs.get('code')
            state = kwargs.get('state')

            if not code or not state:
                return f"Error: Missing code or state. Code: {bool(code)}, State: {state}"

            provider = request.env['kict.oauth2.provider'].sudo().browse(
                int(state))

            if not provider.exists():
                return f"Error: Provider {state} not found"

            # Exchange code for token
            token_data = {
                'grant_type': 'authorization_code',
                'client_id': provider.client_id,
                'client_secret': provider.client_secret,
                'code': code,
                'redirect_uri': provider.redirect_uri or (request.httprequest.url_root + 'oauth/callback'),
            }

            token_response = requests.post(provider.token_url, data=token_data)
            if token_response.status_code != 200:
                return f"Token error: {token_response.status_code} - {token_response.text}"

            token_info = token_response.json()

            # Get user info
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            user_response = requests.get(
                provider.userinfo_url, headers=headers)
            if user_response.status_code != 200:
                return f"User info error: {user_response.status_code} - {user_response.text}"

            user_info = user_response.json()

            # Find or create user
            user = self._find_or_create_user(user_info, token_info, provider)
            if user:
                # Login user directly without password
                request.session.uid = user.id
                request.session.login = user.login
                request.session.session_token = user._compute_session_token(
                    request.session.sid)
                return request.redirect('/web')
            else:
                return f"User creation failed. User info: {user_info}"

        except Exception as e:
            _logger.error(f"OAuth2 callback error: {e}")
            return f"Exception: {str(e)}"

    def _find_or_create_user(self, user_info, token_info, provider):
        """Find or create user from OAuth2 user info"""
        from datetime import datetime, timedelta

        # Extract data from Laravel response structure
        data = user_info.get('data', {})
        email = data.get('email')
        name = data.get('person', {}).get('full_name') or data.get('username')
        username = data.get('username')

        # Extract token data
        access_token = token_info.get('access_token')
        refresh_token = token_info.get('refresh_token')
        expires_in = token_info.get('expires_in', 3600)
        token_expires = datetime.now() + timedelta(seconds=expires_in)

        if not email:
            return None

        user = request.env['res.users'].sudo().search(
            [('login', '=', email)], limit=1)
        if not user:
            # Generate random password for OAuth users
            import secrets
            import string

            # Define character sets
            lowercase = string.ascii_lowercase
            uppercase = string.ascii_uppercase
            digits = string.digits
            special_chars = "!@#$%^&*"

            # Ensure at least one character from each required set
            password_chars = [
                secrets.choice(lowercase),    # At least 1 lowercase
                secrets.choice(uppercase),    # At least 1 uppercase
                secrets.choice(digits),       # At least 1 digit
                secrets.choice(special_chars)  # At least 1 special character
            ]

            # Fill remaining 8 characters randomly from all sets
            all_chars = lowercase + uppercase + digits + special_chars
            password_chars.extend(secrets.choice(all_chars) for _ in range(8))

            # Shuffle the password to randomize character positions
            secrets.SystemRandom().shuffle(password_chars)
            password = ''.join(password_chars)

            user = request.env['res.users'].sudo().create({
                'name': name or email,
                'login': email,
                'email': email,
                'password': password,
                'active': True,
            })

        # Create or update OAuth token
        token = request.env['kict.oauth.user.token'].sudo().search([
            ('user_id', '=', user.id),
            ('provider_id', '=', provider.id)
        ], limit=1)

        token_vals = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires': token_expires,
            'username': username,
        }

        if token:
            token.write(token_vals)
        else:
            token_vals.update({
                'user_id': user.id,
                'provider_id': provider.id,
            })
            request.env['kict.oauth.user.token'].sudo().create(token_vals)

        return user
