from odoo import models, fields, api
from odoo.exceptions import UserError


class DORevisionWizard(models.TransientModel):
    _name = 'do.revision.wizard'
    _description = 'Wizard for DO Revision'

    do_id = fields.Many2one('fleet.do', string='DO', required=True)
    po_line_ids = fields.Many2many(
        'sale.order.line',
        string='Lines to Revise',
        required=True,
        help="Select lines that need to be revised"
    )
    bop_amount = fields.Monetary(
        string='BOP Amount Used',
        currency_field='currency_id',
        compute='_compute_bop_amount',
        store=True,
        readonly=True,
        help="Total amount of BOP (Budget Operation) that has been used"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    do_total_bop = fields.Monetary(currency_field='currency_id', related='do_id.nominal')
    remaining_bop = fields.Monetary(
        string='Remaining BOP',
        currency_field='currency_id',
        compute='_compute_remaining_bop',
        store=True,
        readonly=True
    )

    bop_usage_line_ids = fields.One2many(
        'do.revision.bop.usage.line',
        'wizard_id',
        string='BOP Usage Details'
    )

    remaining_bop_line_ids = fields.One2many(
        'do.revision.remaining.bop.line',
        'wizard_id',
        string='Remaining BOP Details'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)

        if self.env.context.get('default_do_id'):
            do_id = self.env.context['default_do_id']
            do_record = self.env['fleet.do'].browse(do_id)

        return res

    @api.onchange('do_id')
    def _onchange_do_id(self):
        """Update available po_line_ids when DO changes"""
        if self.do_id:
            self.po_line_ids = [(5,)]
        else:
            self.po_line_ids = [(5,)]

    @api.depends('bop_usage_line_ids.amount')
    def _compute_bop_amount(self):
        """Calculate total BOP amount from usage lines"""
        for rec in self:
            rec.bop_amount = sum(rec.bop_usage_line_ids.mapped('amount'))

    @api.depends('bop_amount', 'do_total_bop')
    def _compute_remaining_bop(self):
        for rec in self:
            rec.remaining_bop = rec.do_total_bop - rec.bop_amount

    def action_submit_revision(self):
        """Process the DO revision"""
        if not self.po_line_ids:
            raise UserError("Harap pilih minimal satu Line untuk direvisi.")

        if not self.bop_usage_line_ids:
            raise UserError("Harap input minimal satu detail penggunaan BOP.")

        if self.remaining_bop > 0 and not self.remaining_bop_line_ids:
            raise UserError("Terdapat sisa BOP. Harap input detail sisa BOP.")

        selected_line_ids = self.env['sale.order.line'].browse(self.po_line_ids.ids).mapped('id')
        so_order_line = self.do_id.po_line_ids.filtered(
            lambda x: x.id not in selected_line_ids
        ).sorted(
            lambda ol: ol.bop, reverse=True
        )[0]
        so = so_order_line.order_id
        bop_nominal = self.do_id.nominal

        # Get unique sales orders from selected lines
        sale_orders = self.po_line_ids.mapped('order_id')

        # Cancel the sales orders
        for sale_order in sale_orders:
            if sale_order.state not in ['cancel']:
                try:
                    sale_order.action_cancel()
                    sale_order.write({'is_revised_from_do': True})
                    revised_line_bop = max(sale_order.order_line.mapped('bop'))

                    so.order_line.filtered(
                        lambda line: line.product_id.vehicle_category_id and line.is_line
                    ).write({"is_header": True, 'is_header_from_revision': True, 'prev_bop': revised_line_bop})
                except Exception as e:
                    raise UserError(f"Gagal membatalkan Sales Order {sale_order.name}: {str(e)}")

        # Unlink po_line_ids from DO
        self.do_id.write({
            'po_line_ids': [(3, line.id) for line in self.po_line_ids]
        })
        for line in self.po_line_ids:
            for product in self.do_id.do_product_variant_ids.filtered(lambda x: x.order_id == line.order_id):
                product.sudo().unlink()

        # Build BOP usage details message
        usage_details = "\n".join([
            f"  • {line.description}: {self.currency_id.symbol}{line.amount:,.2f}"
            for line in self.bop_usage_line_ids
        ])

        # Build remaining BOP details message
        remaining_details = ""
        if self.remaining_bop_line_ids:
            remaining_details = "\n\nRincian Sisa BOP:\n" + "\n".join([
                f"  • {line.description}: {self.currency_id.symbol}{line.amount:,.2f}"
                for line in self.remaining_bop_line_ids
            ])

        # Log the revision activity
        message = f"""
        DO Revision completed:
        - Cancelled Sales Orders: {', '.join(sale_orders.mapped('name'))}
        - Revised Lines: {len(self.po_line_ids)} lines
        - BOP Amount Used: {self.currency_id.symbol}{self.bop_amount:,.2f}

        Rincian Penggunaan BOP:
        {usage_details}
        {remaining_details}
        """

        driver = self.do_id.driver_id
        if driver:
            remaining_bop = bop_nominal - self.bop_amount
            if remaining_bop > 0:
                # Build description from remaining BOP lines
                remaining_desc_lines = [
                    f"{line.description}: {self.currency_id.symbol}{line.amount:,.2f}"
                    for line in self.remaining_bop_line_ids
                ]
                description = f"Terdapat sisa BOP pada driver {driver.name} sebesar {self.currency_id.symbol}{remaining_bop:,.2f} dengan kode pengiriman {self.do_id.name}\nRincian: {'; '.join(remaining_desc_lines)}"
            else:
                description = None

            # Prepare BOP usage details
            usage_detail_vals = []
            for usage_line in self.bop_usage_line_ids:
                detail_vals = {
                    'description': usage_line.description,
                    'amount': usage_line.amount,
                }
                # Copy attachments if any
                if usage_line.attachment_ids:
                    detail_vals['attachment_ids'] = [(6, 0, usage_line.attachment_ids.ids)]
                usage_detail_vals.append((0, 0, detail_vals))

            # Prepare remaining BOP details
            remaining_detail_vals = []
            for remaining_line in self.remaining_bop_line_ids:
                detail_vals = {
                    'description': remaining_line.description,
                    'amount': remaining_line.amount,
                }
                # Copy attachments if any
                if remaining_line.attachment_ids:
                    detail_vals['attachment_ids'] = [(6, 0, remaining_line.attachment_ids.ids)]
                remaining_detail_vals.append((0, 0, detail_vals))

            # Store Sisa BOP di Driver with details
            self.env['driver.bop.balance'].create({
                'driver_id': driver.id,
                'do_id': self.do_id.id,
                'total_bop': bop_nominal,
                'used_bop': self.bop_amount,
                'remaining_bop': remaining_bop,
                'description': description,
                'bop_usage_detail_ids': usage_detail_vals,
                'remaining_bop_detail_ids': remaining_detail_vals,
            })


        self.do_id._check_auto_confirm()

        if str(self.do_id.status_document_status).lower() == 'good receive':
            query = """
                UPDATE fleet_do SET status_delivery = %s WHERE id = %s
            """
            self.env.cr.execute(query, ('good_receive', self.do_id.id))

        self.do_id.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Revisi DO Berhasil',
                'message': f'DO {self.do_id.name} telah berhasil direvisi. {len(self.po_line_ids)} Lines telah dibatalkan.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class DORevisionBOPUsageLine(models.TransientModel):
    _name = 'do.revision.bop.usage.line'
    _description = 'DO Revision BOP Usage Line'

    wizard_id = fields.Many2one('do.revision.wizard', string='Wizard', required=True, ondelete='cascade')
    description = fields.Char(string='Keterangan', required=True)
    amount = fields.Monetary(
        string='Jumlah',
        currency_field='currency_id',
        required=True
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'do_revision_bop_usage_attachment_rel',
        'line_id',
        'attachment_id',
        string='Lampiran'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
        string='Currency'
    )


class DORevisionRemainingBOPLine(models.TransientModel):
    _name = 'do.revision.remaining.bop.line'
    _description = 'DO Revision Remaining BOP Line'

    wizard_id = fields.Many2one('do.revision.wizard', string='Wizard', required=True, ondelete='cascade')
    description = fields.Char(string='Keterangan Sisa BOP', required=True)
    amount = fields.Monetary(
        string='Jumlah',
        currency_field='currency_id',
        required=True
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'do_revision_remaining_bop_attachment_rel',
        'line_id',
        'attachment_id',
        string='Lampiran'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
        string='Currency'
    )