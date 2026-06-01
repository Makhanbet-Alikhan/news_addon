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
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """
        Override _name_search (Odoo 17+/19 API) to allow searching
        companies by both name and email address.
        name_get() was removed in Odoo 17 — use _name_search + display_name instead.
        """
        domain = domain or []
        if name:
            domain = ['|', ('name', operator, name), ('email', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
