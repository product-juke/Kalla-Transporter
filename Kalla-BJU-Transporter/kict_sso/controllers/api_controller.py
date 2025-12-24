from odoo import http
from odoo.http import request
import json

class APIController(http.Controller):
    
    @http.route('/api/oauth/token/<int:provider_id>', type='http', auth='user', methods=['GET'])
    def get_oauth_token(self, provider_id):
        """Get valid OAuth token for API calls"""
        try:
            user = request.env.user
            token = user.get_oauth_token(provider_id, auto_refresh=True)
            
            if token:
                return json.dumps({
                    'access_token': token.access_token,
                    'expires': token.token_expires.isoformat() if token.token_expires else None,
                    'provider': token.provider_id.name
                })
            else:
                return json.dumps({'error': 'No valid token found'})
                
        except Exception as e:
            return json.dumps({'error': str(e)})