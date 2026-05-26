import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SocialPreviewWizard(models.TransientModel):
    """
    Wizard: lets the editor preview and manually trigger social publishing
    for an already-published news post.
    """
    _name        = 'news.social.preview.wizard'
    _description = 'Social Publish Preview'

    post_id   = fields.Many2one('news.post', string='News Post', required=True, readonly=True)
    caption   = fields.Text(string='Caption (editable)', required=True)
    send_telegram  = fields.Boolean(string='Send to Telegram',  default=True)
    send_facebook  = fields.Boolean(string='Send to Facebook',  default=True)
    send_instagram = fields.Boolean(string='Send to Instagram', default=True)
    send_twitter   = fields.Boolean(string='Send to Twitter/X', default=True)

    @api.model
    def default_get(self, fields_list):
        res     = super().default_get(fields_list)
        post_id = self.env.context.get('default_post_id') or self.env.context.get('active_id')
        if post_id:
            post = self.env['news.post'].browse(post_id)
            res['post_id'] = post.id
            res['caption'] = post._build_caption()
        return res

    def action_publish(self):
        self.ensure_one()
        config = self.env['dpf.social.config'].sudo()._get_config()
        post   = self.post_id

        if self.send_telegram and config.telegram_enabled:
            post._publish_telegram(config)
        if self.send_facebook and config.facebook_enabled:
            post._publish_via_odoo_social(config, 'facebook')
        if self.send_instagram and config.instagram_enabled:
            post._publish_via_odoo_social(config, 'instagram')
        if self.send_twitter and config.twitter_enabled:
            post._publish_via_odoo_social(config, 'twitter')

        return {
            'type':    'ir.actions.client',
            'tag':     'display_notification',
            'params': {
                'title':   _('Social publish queued'),
                'message': _('The post has been sent to the selected channels. Check the Social Log tab for results.'),
                'type':    'success',
            },
        }
