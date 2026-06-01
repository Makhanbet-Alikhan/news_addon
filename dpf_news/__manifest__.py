{
    'name': 'DPF News',
    'version': '19.0.1.0.0',
    'summary': 'News Portal for Odoo Website',
    'description': '''
        News Portal module for Odoo Website.
        News management, gallery settings, website publishing.
    ''',
    'category': 'Website/Communication',
    'author': 'DPF Custom',
    'depends': ['website', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/news_views.xml',
        'views/news_templates.xml',
        'views/news_menu.xml',
        'data/website_menu.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'dpf_news/static/src/css/news.css',
            'dpf_news/static/src/js/news_gallery.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
