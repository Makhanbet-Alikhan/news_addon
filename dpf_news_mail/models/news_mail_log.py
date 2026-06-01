from odoo import models, fields


class NewsMailLog(models.Model):
    """
    Stores a log entry for every email notification attempt
    made when publishing a news post or using manual send buttons.
    Used to verify delivery status and diagnose sending issues.
    """
    _name = 'news.mail.log'
    _description = 'News Email Notification Log'
    _order = 'create_date desc, id desc'

    post_id = fields.Many2one(
        comodel_name='news.post',
        string='News Post',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='news.company',
        string='Company',
        ondelete='set null',
    )
    company_name = fields.Char(
        string='Company Name',
        help='Stored separately in case the company record is later deleted.',
    )
    email_to = fields.Char(string='Sent To (Email)', required=True)
    status = fields.Selection(
        selection=[
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        string='Status',
        required=True,
        default='sent',
    )
    error_message = fields.Text(
        string='Error Message',
        help='Populated when status is Failed. Contains the exception details.',
    )
    triggered_by = fields.Selection(
        selection=[
            ('publish', 'Auto on Publish'),
            ('manual_selected', 'Manual — Selected Companies'),
            ('manual_all', 'Manual — All Companies'),
        ],
        string='Triggered By',
        default='publish',
    )
    create_date = fields.Datetime(string='Sent At', readonly=True)
