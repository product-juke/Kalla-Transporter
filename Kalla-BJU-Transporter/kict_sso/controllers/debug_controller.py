from odoo import http
from odoo.http import request


class DebugController(http.Controller):

    @http.route('/oauth2/test', type='http', auth='public')
    def test_route(self):
        return "OAuth2 module is working!"

    @http.route('/oauth/simple', type='http', auth='public')
    def simple_oauth(self, **kwargs):
        try:
            provider_id = kwargs.get('provider_id', '1')
            providers = request.env['kict.oauth2.provider'].sudo().search([])
            return f"Provider ID: {provider_id}, Found providers: {len(providers)}"
        except Exception as e:
            return f"Error: {str(e)}"
