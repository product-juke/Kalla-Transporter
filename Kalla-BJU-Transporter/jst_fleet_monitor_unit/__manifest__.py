# -*- coding: utf-8 -*-
{
    'name': 'JST - Fleet Vehicle Monitor Unit',

    'summary': "Add Monitor Unit button to Fleet Vehicle with Share Link integration",

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
    'depends': ['base', 'fleet'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/fleet_vehicle_views.xml',
        'wizard/fleet_monitor_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

