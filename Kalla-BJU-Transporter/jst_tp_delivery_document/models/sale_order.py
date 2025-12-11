from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero
import logging


_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portfolio.view.mixin']

    is_match_do = fields.Boolean('Kesesuaian Surat jalan dengan DO line', store=True)
    is_match_po = fields.Boolean('Kesesuaian Nilai PO di surat jalan dengan yang di DO', store=True)
    attach_doc_complete = fields.Boolean('Document Fisik Lengkap', store=True)
    status_delivery = fields.Selection(string='Status Delivery', selection=[('draft', 'Draft'), ('on_going', 'On Going'),
                                                  ('on_return', 'On Return'), ('good_receive', 'Good Receipt')],
                                       default='draft', store=True)

    # @api.depends('do_ids.status_delivery', 'order_line.attachment', 'order_line.no_surat_jalan')
    # def _compute_delivery_status_so(self):
    #     for rec in self:
    #         if self.is_lms(rec.env.company.portfolio_id.name) and rec.state == 'sale':
    #             for do in rec.do_ids:
    #                 # if all(rec.order_line.mapped('attachment')) and all(rec.order_line.mapped('no_surat_jalan')):
    #                 if rec.is_match_do and rec.is_match_po and rec.attach_doc_complete:
    #                     rec.status_delivery = 'good_receive'
    #                     rec.invoice_status = 'to invoice'
    #                 else:
    #                     rec.status_delivery = do.status_delivery
    #         else:
    #             continue
    
    @api.onchange('is_match_do', 'is_match_po', 'attach_doc_complete', 'so_reference')
    def _onchange_match_flags(self):
        for rec in self:
            if rec.attach_doc_complete and rec.is_match_do and rec.is_match_po and rec.so_reference:
                rec.status_delivery = 'good_receive'
            else:
                rec.status_delivery = 'on_return'
                
    def write(self, vals):
        if self.env.context.get('skip_auto_confirm'):
            return super().write(vals)

        res = super().write(vals)

        interesting = {
            'is_match_po', 'is_match_do', 'attach_doc_complete', 'so_reference'
        }
        if interesting.intersection(vals.keys()):
            try:
                self._check_auto_confirm()
            except Exception:
                _logger.exception("auto confirm failed for SO ids: %s", self.ids)

        return res

    # -----------------------------
    # Helper: ambil semua SO yang terkait ke sebuah DO
    # -----------------------------
    def _sos_for_do(self, do):
        # Kalau DO punya relasi sale_order_ids pakai itu,
        # kalau tidak, fallback search berdasarkan many2many/one2many di SO.do_ids
        sos = getattr(do, 'sale_order_ids', False)
        print(sos)
        if not sos:
            sol_rs = self.env['sale.order.line'].search([('do_id', '=', do.id)])
            sos = sol_rs.mapped('order_id').filtered(lambda so: so.state != 'cancel')
        return sos

    # -----------------------------
    # AUTO CONFIRM
    # -----------------------------
    def _check_auto_confirm(self):
        """
        1) Hitung ulang flag di SO: attach_doc_complete, is_match_do, is_match_po
        2) Jika semua terpenuhi, set status SO & DO ke 'good_receive'/'done'
        3) Jika uncheck (kombinasi tidak terpenuhi), DO balik ke 'approved_by_kacab'
           dan SO ke 'on_return'
        Catatan: semua write di sini pakai context skip_auto_confirm agar tidak rekursi.
        """
        safe_ctx = dict(self.env.context, skip_auto_confirm=True, tracking_disable=True)

        for rec in self:
            # --- 1) Cek kelengkapan dokumen baris SO ---
            if rec.order_line:
                has_all_attach = all(rec.order_line.mapped('attachment'))
                has_all_sj     = all(rec.order_line.mapped('no_surat_jalan'))
                so_attach_ok   = bool(has_all_attach and has_all_sj)
            else:
                so_attach_ok = False
            print(has_all_attach, has_all_sj, so_attach_ok)
            # --- 2) Tentukan flag match_do / match_po terbaru ---
            # Jika mau strict, ganti 'or' jadi 'and'
            new_is_match_do = so_attach_ok or bool(rec.is_match_do)
            new_is_match_po = so_attach_ok or bool(rec.is_match_po)
            print(new_is_match_do, new_is_match_po, so_attach_ok)
            # Tulis flag baru ke SO (hindari rekursi)
            rec.with_context(safe_ctx).write({
                'attach_doc_complete': so_attach_ok,
                'is_match_do': new_is_match_do,
                'is_match_po': new_is_match_po,
            })

            # Kondisi gabungan (padanan: if rec.is_match_do and rec.is_match_po and rec.attach_doc_complete)
            combined_ok = new_is_match_do and new_is_match_po and so_attach_ok

            if combined_ok and not (rec.so_reference and rec.so_reference.strip()):
                raise ValidationError(
                    _("Sales Order %s wajib memiliki SO Reference pelanggan sebelum bisa berstatus Good Receipt.")
                    % rec.name
                )

            # --- 3) Business rule LMS + state sale ---
            is_lms_company = getattr(rec, 'is_lms', None) and rec.is_lms(rec.env.company.portfolio_id.name)
            if not (is_lms_company and rec.state == 'sale'):
                continue

            # Untuk setiap DO terkait: evaluasi across-all SO
            for do in rec.do_ids:
                # Kumpulkan semua SO yang terkait ke DO ini
                sos_for_do = self._sos_for_do(do)

                # Hitung "all_so_ok": semua SO terkait sudah OK (pakai flag tersimpan)
                # NB: rec sendiri baru saja di-update di atas, jadi nilainya up-to-date.
                all_so_ok = all(
                    bool(so.attach_doc_complete and so.is_match_do and so.is_match_po and so.so_reference)
                    for so in sos_for_do
                )
                
                # temporary check validation with popup
                # for so in sos_for_do:  # sos_for_do berisi recordset sale.order
                #     branch = (so.branch_project or '').strip().lower()
                #     if branch != 'lmks':
                #         continue  # hanya enforce untuk LMKS

                #     invoiced_by = (so.contract_invoiced_by or '').strip().lower()
                #     missing = False
                #     label = None

                #     if invoiced_by == 'tonase':
                #         missing = float_is_zero(so.actual_tonase or 0.0, precision_digits=2)
                #         label = 'Tonase'
                #     elif invoiced_by == 'volume':
                #         missing = float_is_zero(so.actual_volume or 0.0, precision_digits=3)
                #         label = 'Volume'
                #     elif invoiced_by == 'ritase':
                #         missing = float_is_zero(so.qty_ritase or 0.0, precision_digits=0)
                #         label = 'Ritase'

                #     if missing:
                #         raise ValidationError(_(
                #             "Sales Order %s wajib mengisi actual %s sebelum berstatus Good Receipt."
                #         ) % (so.name, label or invoiced_by.capitalize()))

                missing_so_refs = sos_for_do.filtered(
                    lambda so: not (so.so_reference and so.so_reference.strip())
                )

                if all_so_ok:
                    if missing_so_refs:
                        missing_names = ", ".join(missing_so_refs.mapped('name'))
                        raise ValidationError(
                            _(
                                "Sales Order berikut wajib memiliki SO Reference pelanggan sebelum Delivery Order %s dapat berstatus Good Receipt: %s"
                            )
                            % (do.name, missing_names)
                        )

                    if not (do.reference and do.reference.strip()):
                        raise ValidationError(
                            _(
                                "Delivery Order %s wajib memiliki DO Reference pelanggan sebelum dapat berstatus Good Receipt."
                            )
                            % do.name
                        )
                    sol_rs = self.env['sale.order.line'].search([('do_id', '=', do.id)])
                    sos = sol_rs.mapped('order_id').filtered(lambda so: so.state != 'cancel')
                    sos.with_context(safe_ctx).write({
                        'status_delivery': 'good_receive',
                        'invoice_status': 'to invoice'
                    })

                    # Semua SO terkait DO ini sudah OK -> DO jadi done & good_receive
                    # SO saat ini diset good_receive (opsional: set semua SO lain juga)
                    
                    updates_do = {
                        'is_match_do': True,
                        'is_match_po': True,
                        'attach_doc_complete': True,
                        'status_delivery': 'good_receive',
                        'status_document_status': 'Good Receive',  # jika field ini ada
                        'state': 'done',
                        # 'status_do': "DO Match",
                    }
                    do.with_context(safe_ctx).write(updates_do)

                    # (Opsional, jaga konsistensi semua SO terkait)
                    # sos_for_do.with_context(safe_ctx).write({'status_delivery': 'good_receive'})

                else:
                    # Ada minimal 1 SO yg belum OK -> DO jangan done
                    # Jika sebelumnya sudah done dan sekarang di-uncheck, balikan state DO
                    # + tandai SO ini 'on_return'
                    revert_do = {
                        'state': 'approved_by_kacab',
                        # kalau mau, DO-nya juga punya status_delivery on_return
                        'status_delivery': 'on_return',
                        'status_document_status': 'On Return',  # jika field ada
                    }
                    do.with_context(safe_ctx).write(revert_do)

                    # SO ini on_return
                    if combined_ok:
                        rec.with_context(safe_ctx).write({'status_delivery': 'good_receive'})
                    else:
                        # SO ini on_return
                        rec.with_context(safe_ctx).write({'status_delivery': 'on_return'})
