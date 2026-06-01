from odoo import models, fields


class NewsSocialLog(models.Model):
    _name = 'news.social.log'
    _description = 'News Social Publish Log'
    _order = 'create_date desc'

    post_id = fields.Many2one('news.post', string='News Post', ondelete='cascade', required=True)
    channel = fields.Selection([
        ('telegram', 'Telegram'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('twitter', 'Twitter/X'),
    ], string='Channel', required=True)
    status = fields.Selection([
        ('sent', 'Sent ✅'),
        ('error', 'Error ❌'),
    ], string='Status', required=True, default='sent')
    message = fields.Text(string='Details / Error')
    create_date = fields.Datetime(string='Sent At', readonly=True)
