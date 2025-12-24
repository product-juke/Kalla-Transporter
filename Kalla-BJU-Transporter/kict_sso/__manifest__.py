{
    'name': 'KICT SSO',
    'version': '17.0.1.0.2',
    'category': 'Authentication',
    'summary': 'KICT Single Sign-On OAuth2 Authorization Code',
    'author': "Kalla ICT (Muhammad Mahendra)",
    'website': "https://kalla.co.id/",
    'maintainer': "Kalla ICT",
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/oauth2_provider_views.xml',
        'views/oauth_user_token_views.xml',
        'views/res_users_views.xml',
        'views/login_template.xml',
        # 'data/oauth2_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'kict_sso/static/src/css/oauth_providers.css',
        ],
        'web.assets_backend': [
            'kict_sso/static/src/css/oauth_providers.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}
