# -*- coding: utf-8 -*-
{
    'name': "jst_tp_utilization",

    'summary': "Pembuatan Data Mart Vehicle Utilization",

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
    'depends': ['base', 'jst_demo_kalla_bju_transporter'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/mart_utilization.xml',
        'views/mart_revenue.xml',

        # data import
        'data/utilization_details_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    "installable": True,
    "application": True,
}

