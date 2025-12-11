from odoo import http
from odoo.http import request


class CustomInvoiceController(http.Controller):

    @http.route('/report/pdf/custom_invoice/<int:invoice_id>', type='http', auth='user')
    def custom_invoice_pdf(self, invoice_id, **kwargs):
        """Generate custom invoice PDF via URL"""
        invoice = request.env['account.move'].browse(invoice_id)
        if not invoice.exists():
            return request.not_found()

        # Generate PDF report
        pdf = request.env.ref('jst_custom_pdf_report.action_report_custom_invoice')._render_qweb_pdf([invoice_id])[0]

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition',
             'attachment; filename="Custom_Invoice_{}.pdf"'.format(invoice.name.replace('/', '_')))
        ]

        return request.make_response(pdf, headers=pdfhttpheaders)