
import re
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

NEWS_TYPE_SELECTION = [
    ('news',          'News'),
    ('announcements', 'Announcements'),
    ('pre_releases',  'Pre-releases'),
]
TYPE_URL = {
    'news':          '/news',
    'announcements': '/announcements',
    'pre_releases':  '/pre-releases',
}


class NewsPost(models.Model):
    _name        = 'news.post'
    _description = 'News Post'
    _order       = 'date desc, id desc'
    _inherit     = ['website.published.mixin']

    # ── Core fields ──────────────────────────────────────────────────────────
    name         = fields.Char(string='Title', required=True, translate=True)
    date         = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    content      = fields.Html(string='Content', required=True, translate=True, sanitize=False)
    news_type    = fields.Selection(selection=NEWS_TYPE_SELECTION, string='News Type',
                                    required=True, default='news')
    image_ids    = fields.One2many('news.post.image', 'post_id', string='Images')
    excerpt      = fields.Char(string='Excerpt', compute='_compute_excerpt', store=False)
    website_url  = fields.Char(compute='_compute_website_url', store=True)
    main_image   = fields.Binary(compute='_compute_main_image', store=False)
    main_image_fname = fields.Char(compute='_compute_main_image', store=False)

    # ── Gallery settings ─────────────────────────────────────────────────────
    gallery_layout     = fields.Selection([
        ('side',   'Main + thumbnails on the right'),
        ('bottom', 'Main + thumbnails below'),
    ], string='Gallery Layout', default='side')
    main_image_width   = fields.Integer(string='Main Photo Width (%)', default=70)
    main_image_height  = fields.Integer(string='Main Photo Height (px)', default=500)
    thumb_height       = fields.Integer(string='Thumbnail Height (px)', default=120)

    # ── Social publishing ─────────────────────────────────────────────────────
    social_auto_publish = fields.Boolean(
        string='Auto-publish to Social Media',
        default=True,
        help='When enabled, publishing this post will automatically send it to all active social channels.',
    )
    social_log_ids = fields.One2many('news.social.log', 'post_id', string='Social Publish Log')
    social_status  = fields.Selection([
        ('not_sent', 'Not sent'),
        ('partial',  'Partially sent'),
        ('sent',     'Fully sent'),
        ('error',    'Error'),
    ], string='Social Status', default='not_sent', compute='_compute_social_status', store=True)

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('name', 'news_type')
    def _compute_website_url(self):
        for rec in self:
            base = TYPE_URL.get(rec.news_type or 'news', '/news')
            rec.website_url = '%s/%d' % (base, rec.id) if rec.id else base

    @api.depends('image_ids', 'image_ids.image', 'image_ids.sequence')
    def _compute_main_image(self):
        for rec in self:
            first = rec.image_ids.sorted('sequence')[:1]
            rec.main_image       = first.image if first else False
            rec.main_image_fname = first.name  if first else False

    @api.depends('content')
    def _compute_excerpt(self):
        for rec in self:
            raw   = rec.content or ''
            clean = re.sub(r'<[^>]+>', ' ', raw)
            clean = re.sub(r'\s+', ' ', clean).strip()
            rec.excerpt = (clean[:157] + '...') if len(clean) > 160 else clean

    @api.depends('social_log_ids', 'social_log_ids.status')
    def _compute_social_status(self):
        for rec in self:
            logs = rec.social_log_ids
            if not logs:
                rec.social_status = 'not_sent'
            elif all(l.status == 'sent' for l in logs):
                rec.social_status = 'sent'
            elif any(l.status == 'sent' for l in logs):
                rec.social_status = 'partial'
            else:
                rec.social_status = 'error'

    # ── Website publish button (override) ────────────────────────────────────
    def website_publish_button(self):
        self.ensure_one()
        was_published = self.is_published
        self.is_published = not self.is_published
        if self.is_published and not was_published and self.social_auto_publish:
            self._social_publish_all()
        return False

    def open_website_url(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.website_url, 'target': 'new'}

    # ── Social publish dispatcher ─────────────────────────────────────────────
    def _social_publish_all(self):
        """Dispatch to all enabled channels from DPF Social Config."""
        self.ensure_one()
        config = self.env['dpf.social.config'].sudo()._get_config()
        if not config:
            return
        if config.telegram_enabled:
            self._publish_telegram(config)
        if config.facebook_enabled:
            self._publish_via_odoo_social(config, 'facebook')
        if config.instagram_enabled:
            self._publish_via_odoo_social(config, 'instagram')
        if config.twitter_enabled:
            self._publish_via_odoo_social(config, 'twitter')

    def _build_caption(self, max_len=2000):
        """Build a rich post caption for social media."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        url      = base_url.rstrip('/') + self.website_url
        caption  = '%s\n\n%s\n\n🔗 %s' % (self.name, self.excerpt or '', url)
        if len(caption) > max_len:
            caption = caption[:max_len - 3] + '...'
        return caption

    def _log_social(self, channel, status, message=''):
        self.env['news.social.log'].sudo().create({
            'post_id': self.id,
            'channel': channel,
            'status':  status,
            'message': message or '',
        })

    # ── Telegram (direct Bot API — no extra module needed) ───────────────────
    def _publish_telegram(self, config):
        import requests
        token   = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            self._log_social('telegram', 'error', 'Bot token or chat_id not configured')
            return

        caption = self._build_caption(max_len=1024)
        first_img = self.image_ids.sorted('sequence')[:1]

        try:
            if first_img and first_img.image:
                import base64, io
                img_bytes = base64.b64decode(first_img.image)
                r = requests.post(
                    'https://api.telegram.org/bot%s/sendPhoto' % token,
                    data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': ('photo.jpg', io.BytesIO(img_bytes), 'image/jpeg')},
                    timeout=15,
                )
            else:
                r = requests.post(
                    'https://api.telegram.org/bot%s/sendMessage' % token,
                    data={'chat_id': chat_id, 'text': caption, 'parse_mode': 'HTML'},
                    timeout=15,
                )
            r.raise_for_status()
            self._log_social('telegram', 'sent', 'OK (message_id=%s)' % r.json().get('result', {}).get('message_id', ''))
        except Exception as e:
            _logger.error('DPF News Telegram publish error: %s', e)
            self._log_social('telegram', 'error', str(e))

    # ── Facebook / Instagram / Twitter via Odoo Social Marketing module ───────
    def _publish_via_odoo_social(self, config, platform):
        """
        Use Odoo's built-in `social.post` model (module: social_media) if available.
        Falls back to logging a clear instruction if the module is not installed.
        """
        SocialPost = self.env.get('social.post')
        if SocialPost is None:
            self._log_social(
                platform, 'error',
                'Odoo Social Marketing app (social_media) is not installed. '
                'Install it from Apps → Social Marketing to enable %s publishing.' % platform.capitalize()
            )
            return

        # Find matching account by media_type
        media_type_map = {
            'facebook':  'facebook',
            'instagram': 'instagram',
            'twitter':   'twitter',
        }
        account = self.env['social.account'].sudo().search([
            ('media_type', '=', media_type_map.get(platform, platform)),
            ('has_account_link', '=', True),
        ], limit=1)

        if not account:
            self._log_social(
                platform, 'error',
                'No connected %s account found in Social Marketing → Accounts.' % platform.capitalize()
            )
            return

        caption = self._build_caption(max_len=2000)
        vals = {
            'message':     caption,
            'account_ids': [(4, account.id)],
            'state':       'posted',
        }

        # Attach first image if available
        first_img = self.image_ids.sorted('sequence')[:1]
        if first_img and first_img.image:
            try:
                import base64
                attachment = self.env['ir.attachment'].sudo().create({
                    'name':     'news_post_%d_%s.jpg' % (self.id, platform),
                    'datas':    first_img.image,
                    'res_model': 'news.post',
                    'res_id':   self.id,
                    'mimetype': 'image/jpeg',
                })
                vals['image_ids'] = [(4, attachment.id)]
            except Exception as e:
                _logger.warning('DPF News: Could not attach image for %s: %s', platform, e)

        try:
            post = SocialPost.sudo().create(vals)
            self._log_social(platform, 'sent', 'social.post id=%d' % post.id)
        except Exception as e:
            _logger.error('DPF News social post (%s) error: %s', platform, e)
            self._log_social(platform, 'error', str(e))


    def action_open_social_wizard(self):
        """Open the social preview wizard for manual re-publish."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Publish to Social Media',
            'res_model': 'news.social.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_post_id': self.id,
            },
        }


class NewsPostImage(models.Model):
    _name        = 'news.post.image'
    _description = 'News Post Image'
    _order       = 'sequence, id'

    post_id     = fields.Many2one('news.post', string='News Post', required=True, ondelete='cascade')
    name        = fields.Char(string='Caption', default='Image')
    image       = fields.Binary(string='Image', required=True, attachment=True)
    image_fname = fields.Char(string='Filename')
    sequence    = fields.Integer(string='Sequence', default=10)
