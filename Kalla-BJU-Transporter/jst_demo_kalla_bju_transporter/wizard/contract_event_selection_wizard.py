from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ContractEventSelectionWizard(models.TransientModel):
    _name = 'contract.event.selection.wizard'
    _description = 'contract.event.selection.wizard'

    contract_id = fields.Many2one('create.contract')
    partner_id = fields.Many2one('res.partner')
    product_id = fields.Many2one('product.product', 'CATEGORY UNIT')
    origin_id = fields.Many2one('master.origin', 'ORIGIN')
    destination_id = fields.Many2one('master.destination', 'DESTINATION')
    distance = fields.Integer('DISTANCE (KM)')
    sla = fields.Integer('SLA DELIVERY (Day)')
    qty_tonase = fields.Float('TONASE (Ton)')
    qty_kubikasi = fields.Float('VOLUME (Kubikasi)')
    qty_unit = fields.Float('UNIT/PCS')
    qty_dus = fields.Float('DUS/BOX')
    qty_ritase = fields.Float('RITASE')
    qty_target_tonase = fields.Float('TARGET TONASE')
    qty_target_ritase = fields.Float('TARGET RITASE (Trucking)')
    qty_actual_tonase = fields.Float('ACTUAL TONASE')
    currency_id = fields.Many2one('res.currency', related='contract_id.company_id.currency_id')
    price = fields.Monetary('PRICE', currency_field='currency_id')
    bop = fields.Monetary('BOP', currency_field='currency_id', compute="compute_bop", readonly=True)
    id_contract = fields.Char('CE. CODE')
    is_handling_type = fields.Boolean('HANDLING')
    is_line = fields.Boolean('LINE')
    start_date_event = fields.Date('Start Date Event')
    end_date_event = fields.Date('End Date Event')
    active = fields.Boolean('Status', default=True)
    start_date = fields.Date('Start Date', tracking=True)
    end_date = fields.Date('End Date', tracking=True)
    contract_line_ids = fields.Many2many(
        'create.contract.line',
        string='Contract Lines',
        store=False
    )
    selected_line_id = fields.Many2one('create.contract.line', string='Selected Line')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract_id = self.env.context.get('default_contract_id')
        branch_project = self.env.context.get('branch_project')

        if contract_id:
            lines = self.env['create.contract.line'].search([
                ('contract_id', '=', contract_id),
                ('contract_id.branch_project', '=', branch_project),
            ])

            res['contract_line_ids'] = [(6, 0, lines.ids)]

            selected_line = lines.filtered(lambda l: l.is_line)
            if selected_line:
                res['selected_line_id'] = selected_line[0].id

        return res

    def action_confirm_selected_contract_line(self):
        self.ensure_one()

        if not self.selected_line_id:
            raise UserError("Pilih salah satu contract line terlebih dahulu.")

        selected_line = self.selected_line_id
        contract = selected_line.contract_id

        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        if not sale_order:
            raise UserError("Sale Order tidak ditemukan.")

        product_detail = []
        rec = self.env['create.contract'].search([
            ('id', '=', contract.id)
        ])

        is_vli_or_customer_tam = (contract.product_name == 'VLI' or contract.partner_id.is_tam)
        checked_products = rec.product_detail_ids.filtered(lambda pd: pd.go_to_so)
        if len(checked_products) < 1 and is_vli_or_customer_tam:
            raise ValidationError(_(f"Belum ada baris yang di centang pada tab \"Detail Order\""))

        details = checked_products if is_vli_or_customer_tam else []
        # Kumpulkan detail produk
        for line in details:
            product_detail.append((0, 0, {
                'product_id': line.product_id.id,
                'product_code': line.product_code,
                'ce_code': line.ce_code.id_contract,
                'name': line.product_description if line.product_description else line.product_id.name,
                'price_unit': line.unit_price,
                'quantity': line.qty,
                'uom_id': line.uom_id.id if line.uom_id else line.product_id.uom_id.id,
                'qty_tonase': line.qty_tonase,
                'qty_ritase': line.qty_ritase,
                'qty_kubikasi': line.qty_kubikasi,
                'origin_id': line.origin_id.id,
                'destination_id': line.destination_id.id,
            }))

        analytic_distribution = None
        if rec.product_category_id and rec.product_category_id.id:
            analytic_account = self.env['sale.order']._get_or_create_analytic_account(rec.product_category_id.name)
            if analytic_account:
                analytic_distribution = {str(analytic_account.id): 100}

        # Data order line
        values = {
            'product_id': selected_line.product_id.id,
            'name': selected_line.product_id.name,
            'price_unit': selected_line.price,
            'origin_id': selected_line.origin_id.id,
            'destination_id': selected_line.destination_id.id,
            'is_line': True,
            'is_handling_type': selected_line.is_handling_type,
            'id_contract': selected_line.id_contract,
            'distance': selected_line.distance,
            'sla': selected_line.sla,
            'qty_tonase': selected_line.qty_tonase,
            'qty_kubikasi': selected_line.qty_kubikasi,
            'qty_unit': selected_line.qty_unit if not is_vli_or_customer_tam else 0,
            'qty_dus': selected_line.qty_dus,
            'qty_ritase': selected_line.qty_ritase,
            'qty_target_ritase': selected_line.qty_target_ritase,
            'bop': selected_line.bop,
            'analytic_distribution': analytic_distribution,
            # 'invoice_policy': rec.invoice_policy,
            'tax_id': selected_line.product_id.partner_tax_ids.filtered(lambda x: x.partner_id.id == rec.partner_id.id).tax_ids if selected_line.product_id.partner_tax_ids.filtered(lambda x: x.partner_id.id == rec.partner_id.id) else None
        }

        # Data sale order umum
        common_vals = {
            'opportunity_id': rec.crm_id.id,
            'partner_id': rec.partner_id.id,
            'company_id': rec.company_id.id,
            'origin': rec.name,
            'user_id': rec.responsible_id.id,
            'team_id': rec.crm_id.team_id.id,
            'contract_id': rec.id,
            'branch_project': rec.branch_project,
            'product_category_id': rec.product_category_id.id,
            'delivery_category_id': rec.delivery_category_id.id,
            'sale_order_option_ids': product_detail,
            'invoice_policy': rec.invoice_policy,
        }

        # Update / tambahkan order line
        if sale_order.order_line:
            sale_order.order_line = [(1, sale_order.order_line[0].id, values)]
        else:
            sale_order.order_line = [(0, 0, values)]

        # Set field umum
        sale_order.write(common_vals)
        sale_order.sudo().write({
            'invoice_policy': rec.invoice_policy
        })

        return {'type': 'ir.actions.act_window_close'}

class CreateContractLine(models.Model):
    _inherit = 'create.contract.line'

    def action_select_this_line(self):
        """Action to select this line in wizard context"""
        # Get the active wizard from context (if called from wizard view)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        wizard_id = self.env.context.get('wizard_id')

        # Alternative approach using wizard_id from context
        if wizard_id:
            wizard = self.env['contract.event.selection.wizard'].browse(wizard_id)
            if wizard.exists():
                wizard.selected_line_id = self.id
                wizard.action_confirm_selected_contract_line()

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_contract_event_selection_wizard(self):
        self.ensure_one()
        return {
            'name': _('Select Contract event'),
            'type': 'ir.actions.act_window',
            'res_model': 'contract.event.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.contract_id.id,
                'default_partner_id': self.partner_id.id,
                'branch_project': self.branch_project,
            },
        }