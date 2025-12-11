# -*- coding: utf-8 -*-
{
    'name': "Custom Invoice Journal Items",

    'summary': "Auto create journal items for Uang Muka and HPP Biaya Mobilisasi",

    'description': """
    """,

    'author': "Juke Solusi Teknologi",
    'website': "https://www.jukesolutions.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'jst_tp_company', 'jst_demo_kalla_bju_transporter'],

    # always loaded
    'data': [
        'data/account_data.xml',
        'views/res_config_settings.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'auto_install': False,
}

