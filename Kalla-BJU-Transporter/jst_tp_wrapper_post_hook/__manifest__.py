# __manifest__.py
{
    'name': 'wrapper_hook',
    'version': '17.0.1.0.0',
    'depends': ['base', 'sale', 'jst_demo_kalla_bju_transporter'],  # add what you actually depend on
    'post_init_hook': 'post_init_hook',
    'data': [
        'data/wrapper.xml',
        # 'views/views.xml',
    ],
}
