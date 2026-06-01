{
    'name': 'DPF News Social',
    'version': '19.0.1.0.0',
    'summary': 'Social publishing extension for DPF News',
    'description': '''
        Adds manual and automatic social publishing to DPF News.
        Supports Telegram, Facebook, Instagram, and Twitter/X.
    ''',
    'category': 'Website/Communication',
    'author': 'DPF Custom',
    'depends': ['dpf_news'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/social_preview_wizard_views.xml',
        'views/social_config_views.xml',
        'views/news_views.xml',
        'views/news_menu.xml',
        'data/social_config_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
