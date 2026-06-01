{
    'name': 'DPF News - Mail Notifications',
    'version': '19.0.1.0.0',
    'summary': 'Send email notifications to subscriber companies when news is published',
    'description': '''
        Extension addon for DPF News module.
        - Manage subscriber companies with email addresses.
        - Select companies via checkboxes when creating a news post.
        - Auto-send email on publish to selected companies.
        - Button to send to all active subscriber companies at once.
    ''',
    'category': 'Website/Communication',
    'author': 'DPF Custom',
    'depends': ['dpf_news', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'views/news_company_views.xml',
        'views/news_mail_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
