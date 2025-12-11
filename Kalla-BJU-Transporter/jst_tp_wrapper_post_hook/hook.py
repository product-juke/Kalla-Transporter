# hook.py
def _replace_menu_action(env, base_xmlid, wrapper_xmlid):
    """Replace all ir.ui.menu.action pointing to base act_window → wrapper server action."""
    base = env.ref(base_xmlid, raise_if_not_found=False)
    wrapper = env.ref(wrapper_xmlid, raise_if_not_found=False)
    if not base or not wrapper:
        return 0

    base_key = f'ir.actions.act_window,{base.id}'
    wrapper_key = f'ir.actions.server,{wrapper.id}'

    menus = env['ir.ui.menu'].sudo().search([('action', '=', base_key)])
    if menus:
        menus.sudo().write({'action': wrapper_key})
    return len(menus)


def post_init_hook(env):
    """Odoo 17 calls this hook with ENV, not (cr, registry)."""
    # list of (base_xmlid, wrapper_xmlid)
    mappings = [
        ('sale.action_orders', 'jst_tp_wrapper_post_hook.action_sale_order_wrapper'),
        ('sale.action_quotations_with_onboarding', 'jst_tp_wrapper_post_hook.action_sale_order_quotation_wrapper'),
        ('jst_demo_kalla_bju_transporter.action_orders_to_invoice_lms', 'jst_tp_wrapper_post_hook.action_sale_order_invoice_wrapper'),
        # add more pairs here as needed
    ]

    for base_xmlid, wrapper_xmlid in mappings:
        _replace_menu_action(env, base_xmlid, wrapper_xmlid)


