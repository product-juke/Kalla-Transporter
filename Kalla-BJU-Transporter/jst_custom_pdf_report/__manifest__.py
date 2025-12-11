{
    'name': 'JST - Custom Report Print',
    'category': 'Uncategorized',
    'version': '0.1',
    'summary': 'Custom PDF Generator',
    'description': """
        Custom Print Module
        ===========================

        This module adds a custom "Print Invoice" button that generates
        PDF invoice in custom format similar to PT. QWERTY ASAS format.
    """,
    'author': "Juke Solusi Teknologi",
    'website': "https://www.jukesolutions.com",
    'depends': ['account', 'base'],
    'data': [
        'views/account_move_views.xml',
        'reports/custom_invoice_report.xml',
        'reports/custom_invoice_template.xml',
    ],
    'assets': {},
    'installable': True,
    'auto_install': False,
    'application': True,
}