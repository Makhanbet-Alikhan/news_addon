# -*- coding: utf-8 -*-
"""
post_init_hook — creates multilingual website menu items for:
  News          /news
  Announcements /announcements
  Pre-releases  /pre-releases

Translations: KZ, RU, EN
"""

_MENUS = [
    {
        'key': 'news_portal.website_menu_news',
        'url': '/news',
        'sequence': 60,
        'translations': {
            'en_US': 'News',
            'ru_RU': 'Новости',
            'kk_KZ': 'Жаңалықтар',
        },
    },
    {
        'key': 'news_portal.website_menu_announcements',
        'url': '/announcements',
        'sequence': 61,
        'translations': {
            'en_US': 'Announcements',
            'ru_RU': 'Объявления',
            'kk_KZ': 'Хабарландырулар',
        },
    },
    {
        'key': 'news_portal.website_menu_pre_releases',
        'url': '/pre-releases',
        'sequence': 62,
        'translations': {
            'en_US': 'Pre-releases',
            'ru_RU': 'Пре-релизы',
            'kk_KZ': 'Алдын ала шығарылымдар',
        },
    },
]


def post_init_hook(env):
    """Create / update website menu items with translations."""
    Website = env['website']
    Menu = env['website.menu']
    websites = Website.search([])

    # Get installed languages
    installed_langs = {code for code, _ in env['res.lang'].get_installed()}

    for website in websites:
        parent = Menu.search([
            ('parent_id', '=', False),
            ('website_id', '=', website.id),
        ], limit=1)
        if not parent:
            # fallback: find any root menu
            parent = Menu.search([('website_id', '=', website.id)], limit=1)

        for menu_def in _MENUS:
            existing = Menu.search([
                ('url', '=', menu_def['url']),
                ('website_id', '=', website.id),
            ], limit=1)

            # Default name is English
            default_name = menu_def['translations'].get('en_US', list(menu_def['translations'].values())[0])

            if not existing:
                existing = Menu.create({
                    'name': default_name,
                    'url': menu_def['url'],
                    'parent_id': parent.id if parent else False,
                    'website_id': website.id,
                    'sequence': menu_def['sequence'],
                })

            # Write translations via ir.translation (Odoo 17+/19 approach)
            for lang_code, translated_name in menu_def['translations'].items():
                if lang_code in installed_langs:
                    existing.with_context(lang=lang_code).write({'name': translated_name})
