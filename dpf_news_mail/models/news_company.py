from odoo import models, fields, api


class NewsCompany(models.Model):
    """
    Represents a subscriber company that can receive
    email notifications when a news post is published.
    """
    _name = 'news.company'
    _description = 'News Subscriber Company'
    _order = 'name'

    name = fields.Char(string='Company Name', required=True)
    email = fields.Char(string='Email Address', required=True)
    active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('email_unique', 'UNIQUE(email)', 'A company with this email already exists!'),
    ]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Allow searching companies by name or email."""
        args = args or []
        if name:
            args = ['|', ('name', operator, name), ('email', operator, name)] + args
        return self.search(args, limit=limit).name_get()
