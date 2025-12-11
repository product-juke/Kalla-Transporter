# -*- coding: utf-8 -*-
{
    'name': "Integration BJU (LMS)",

    'summary': "Integration API BJU",

    'description': """
    """,

    'author': "Juke Solusi Teknologi",
    'website': "https://www.jukesolutions.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/17.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'account_accountant', 'sale', 'queue_job', 'web', 'sale_invoice_policy', 'jst_demo_kalla_bju_transporter', 'jst_oracle_sync_feedback', 'jst_tp_company'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/res_config_setting.xml',
        'views/res_company.xml',
        'views/res_partner.xml',
        'views/sale_order.xml',
        'views/account_move.xml',
        'views/account_payment_oracle.xml',
        'views/account_payment.xml',
        'views/account_tax.xml',
        'data/ir_cron.xml',
        'data/supplier_product_service.xml',
        'views/hr_employee.xml',
    ],
    "installable": True,
    "application": True,
}

