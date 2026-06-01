{
    'name': 'DPF News - Mail Notifications',
    'version': '19.0.1.0.0',
    'summary': 'Send news email notifications to subscribed companies',
    'description': '''
        Extension for DPF News module.
        Allows adding companies with email addresses.
        When publishing a news post, sends email notifications
        to selected companies. Also supports sending to all companies at once.
    ''',
    'category': 'Website/Communication',
    'author': 'DPF Custom',
    'depends': ['dpf_news', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/news_company_views.xml',
        'views/news_mail_views.xml',
        'data/mail_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
