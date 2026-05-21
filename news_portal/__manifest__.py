{
    'name': 'News Portal',
    'version': '19.0.2.0.0',
    'summary': 'Publish and manage news articles on your website',
    'description': """
        News Portal module for Odoo Website.
        - Create and manage news articles
        - Multiple images per news (gallery with main image switcher)
        - Publish / Unpublish from backend and frontend
        - Dedicated /news, /announcements, /pre-releases website pages
        - News detail page with interactive image gallery
        - News types: News, Announcements, Pre-releases
        - Multilingual website menu tabs (KZ, RU, EN)
    """,
    'category': 'Website',
    'author': 'Custom',
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
            'news_portal/static/src/css/news.css',
            'news_portal/static/src/js/news_gallery.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
