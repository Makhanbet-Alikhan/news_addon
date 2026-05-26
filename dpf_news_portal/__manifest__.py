{
    'name': 'DPF News Portal',
    'version': '19.0.3.2.0',
    'summary': 'News, Announcements & Pre-releases with Auto Social Publishing',
    'description': '''
        News Portal module for Odoo Website.
        Auto-publish to Telegram, Facebook, Instagram, Twitter/X on news publish.
    ''',
    'category': 'Website/Communication',
    'author': 'DPF Custom',
    'depends': ['website', 'web'],
    'data': [
        'security/ir.model.access.csv',
        # Load order matters: each file must come AFTER files it references
        'wizard/social_preview_wizard_views.xml',   # no deps
        'views/social_config_views.xml',             # no deps
        'views/news_views.xml',                      # refs wizard action (loaded above)
        'views/news_templates.xml',                  # no deps
        'views/news_menu.xml',                       # refs actions from all views above
        'data/website_menu.xml',
        'data/social_config_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'dpf_news_portal/static/src/css/news.css',
            'dpf_news_portal/static/src/js/news_gallery.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
