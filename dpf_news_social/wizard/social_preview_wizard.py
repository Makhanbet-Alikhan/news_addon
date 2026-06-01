from odoo import models, fields, api, _


class SocialPreviewWizard(models.TransientModel):
    _name = 'news.social.preview.wizard'
    _description = 'Social Publish Preview'

    post_id = fields.Many2one('news.post', string='News Post', required=True, readonly=True)
    caption = fields.Text(string='Preview (Telegram message)', required=True)
    send_telegram = fields.Boolean(string='Send to Telegram', default=True)
    send_facebook = fields.Boolean(string='Send to Facebook', default=True)
    send_instagram = fields.Boolean(string='Send to Instagram', default=True)
    send_twitter = fields.Boolean(string='Send to Twitter/X', default=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        post_id = self.env.context.get('default_post_id') or self.env.context.get('active_id')
        if post_id:
            post = self.env['news.post'].browse(post_id)
            res['post_id'] = post.id
            # Show exactly what will be sent to Telegram
            text, url = post._build_telegram_message()
            res['caption'] = text + '\n\n🔗 ' + url
        return res

    def action_publish(self):
        self.ensure_one()
        config = self.env['dpf.social.config'].sudo()._get_config()
        post = self.post_id
        if self.send_telegram and config.telegram_enabled:
            post._publish_telegram(config)
        if self.send_facebook and config.facebook_enabled:
            post._publish_facebook(config)
        if self.send_instagram and config.instagram_enabled:
            post._publish_instagram(config)
        if self.send_twitter and config.twitter_enabled:
            post._publish_twitter(config)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Done'),
                'message': _('Post sent to selected channels. Check Social Log for results.'),
                'type': 'success',
            },
        }
