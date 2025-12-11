from odoo import api, fields, models, tools, _
from odoo.tools.safe_eval import safe_eval
import json
import time
import re
import requests
from odoo.exceptions import UserError, ValidationError, AccessError
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    printer_data = fields.Text(string="Printer Data", required=False, readonly=True)

    def print_dotmatrix(self):
        url = self.env['ir.config_parameter'].sudo().get_param('dotmatrix.url')
        notif = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
        }
        if not url:
            notif.update({'params': {
                'type': 'warning',
                'message': _('Please setup dotmatrix.url in system parameter')}
            })
            return notif
        try:
            x = requests.post(url, data = {'printer_data': self.printer_data})
            if x.status_code == 200:
                notif.update({'params': {
                    'type': 'success',
                    'message': _('Your request has been successfully')}
                })
                return notif
        except (requests.exceptions.ConnectionError, requests.exceptions.MissingSchema, requests.exceptions.Timeout, requests.exceptions.HTTPError):
            raise AccessError(_('The url that this service requested returned an error. The url it tried to contact was %s', url))

    def generate_printer_data(self):
        for order in self:
            # Pilih template berdasarkan is_tam
            if order.partner_id.is_tam:
                template_name = 'Dot Matrix TAM Sale'
            else:
                template_name = 'Dot Matrix Sale'

            # Ambil template sesuai nama
            tpl = self.env['mail.template'].search([('name', '=', template_name)], limit=1)
            if not tpl:
                raise UserError(f"Template '{template_name}' tidak ditemukan.")

            # Render HTML template
            data = tpl._render_template(tpl.body_html, 'sale.order', [order.id], engine='qweb')

            # Hapus semua tag HTML → jadi teks polos
            comp = re.compile('<.*?>')
            text = re.sub(comp, '', data[order.id])

            # Simpan ke field printer_data
            order.printer_data = text

