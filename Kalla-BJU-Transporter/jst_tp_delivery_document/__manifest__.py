# -*- coding: utf-8 -*-
{
    'name': "jst_tp_delivery_document",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'jst_demo_kalla_bju_transporter'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/sale_delivery_document.xml',
        'views/fleet_do.xml',
        'views/bop_list.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

