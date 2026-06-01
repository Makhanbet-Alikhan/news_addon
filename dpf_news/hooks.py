_MENUS = [
    {'url': '/news', 'sequence': 60,
     'translations': {'en_US': 'News', 'ru_RU': 'Новости', 'kk_KZ': 'Жаңалықтар'}},
]


def post_init_hook(env):
    Website = env['website']
    Menu = env['website.menu']
    websites = Website.search([])
    installed_langs = {code for code, _ in env['res.lang'].get_installed()}

    for website in websites:
        parent = Menu.search([
            ('parent_id', '=', False),
            ('website_id', '=', website.id),
        ], limit=1)
        if not parent:
            parent = Menu.search([('website_id', '=', website.id)], limit=1)

        for menu_def in _MENUS:
            existing = Menu.search([
                ('url', '=', menu_def['url']),
                ('website_id', '=', website.id),
            ], limit=1)
            default_name = menu_def['translations'].get('en_US', list(menu_def['translations'].values())[0])
            if not existing:
                existing = Menu.create({
                    'name': default_name,
                    'url': menu_def['url'],
                    'parent_id': parent.id if parent else False,
                    'website_id': website.id,
                    'sequence': menu_def['sequence'],
                })
            for lang_code, translated_name in menu_def['translations'].items():
                if lang_code in installed_langs:
                    existing.with_context(lang=lang_code).write({'name': translated_name})
