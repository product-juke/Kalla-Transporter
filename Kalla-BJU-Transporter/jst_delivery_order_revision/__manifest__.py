# -*- coding: utf-8 -*-
{
    'name': "JST - Delivery Order Revision",

    'summary': "Add DO Revision functionality to Fleet DO",

    'description': """
    """,

    'author': "PT. Juke Solusi Teknologi",
    'website': "https://www.jukesolutions.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['jst_demo_kalla_bju_transporter', 'base', 'jst_tp_company'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/fleet_do_views.xml',
        'views/revisi_do_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/fleet_do_use_bop_wizard_views.xml',
        'views/views.xml',
        'views/account_account_views.xml',
        'views/return_bop_wizard.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}

