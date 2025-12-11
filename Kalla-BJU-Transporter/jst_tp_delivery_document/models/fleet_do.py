# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetDo(models.Model):
    _inherit = 'fleet.do'
    _description = 'fleet_do'

    is_match_do = fields.Boolean('Kesesuaian Surat jalan dengan DO line', compute='_compute_status_document',
                                 store=True)
    is_match_po = fields.Boolean('Kesesuaian Nilai PO di surat jalan dengan yang di DO',
                                 compute='_compute_status_document', store=True)
    attach_doc_complete = fields.Boolean('Document Fisik Lengkap', compute='_compute_status_document', store=True)
    status_delivery = fields.Selection(string='Status Delivery', selection=[('draft', 'Draft'), ('on_going', 'On Going'),
                                                  ('on_return', 'On Return'), ('good_receive', 'Good Receipt')],
                                       default='draft', store=True)

    @api.depends('po_line_ids.order_id.is_match_do', 'po_line_ids.order_id.is_match_po', 'po_line_ids.order_id.attach_doc_complete')
    def _compute_status_document(self):
        for rec in self:
            rec.is_match_do = True if False not in rec.po_line_ids.mapped('order_id').mapped('is_match_do') else False
            rec.is_match_po = True if False not in rec.po_line_ids.mapped('order_id').mapped('is_match_po') else False
            rec.attach_doc_complete = True if False not in rec.po_line_ids.mapped('order_id').mapped('attach_doc_complete') else False

    @api.depends(
        'vehicle_id.vehicle_status',
        'po_line_ids.attachment',
        'po_line_ids.no_surat_jalan',
        'po_line_ids.order_id.so_reference',
        'reference'
    )
    def _compute_delivery_status_do(self):
        for rec in self.filtered(lambda x: x.state != 'done'):
            has_all_attachment = all(rec.po_line_ids.mapped('attachment'))
            has_all_sj = all(rec.po_line_ids.mapped('no_surat_jalan'))
            has_so_reference = all(
                so.so_reference and so.so_reference.strip()
                for so in rec.po_line_ids.mapped('order_id')
            )
            has_do_reference = rec.reference and rec.reference.strip()

            for line in rec.po_line_ids:
                if line.do_id.is_already_do_match is True:
                    line.do_id.status_do = 'DO Match'

            if has_all_attachment and has_all_sj and has_so_reference and has_do_reference:
                rec.status_delivery = 'good_receive'
                rec.state = 'done'

                # Saat DO nya DONE, kita set semua SO yang berelasi nya jadi to_invoice
                for line in rec.po_line_ids:
                    so = line.order_id
                    if so.state == 'sale' and so.invoice_status != 'to invoice':
                        so.invoice_status = 'to invoice'
            else:
                rec.status_delivery = rec.vehicle_id.vehicle_status

