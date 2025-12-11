# -*- coding: utf-8 -*-
{
    'name': 'JST High Level Dashboard',
    'version': '17.0.1.0.0',
    'summary': 'Data Mart untuk kebutuhan High Level Dashboard',
    'description': """
""",
    'author': "Juke Solusi Teknologi",
    'website': "https://www.jukesolutions.com",
    'category': 'Uncategorized',
    'depends': [
        'base',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',

        'views/mart_status_vehicle.xml',
        'views/mart_delivery_order.xml',
        'views/mart_target_vehicle.xml',
        'views/mart_delivery_category_revenue.xml',
        'views/mart_delivery_order_revenue.xml',
        'views/mart_vehicle_performance.xml',
        'views/mart_branch_performance.xml',
        'views/mart_customer_invoice.xml',
        'views/mart_customer_contract.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}