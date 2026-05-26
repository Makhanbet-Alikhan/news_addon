import re
import base64
import io
import json
import logging
import urllib.request
import urllib.parse
import urllib.error

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


# ---------------------------------------------------------------------------
# Lightweight multipart helper (replaces requests dependency)
# ---------------------------------------------------------------------------

def _multipart_post(url, fields, files=None):
    """
    POST multipart/form-data using only stdlib urllib.
    fields: dict of str->str
    files:  dict of name -> (filename, bytes, content_type)
    Returns (status_code, response_dict)
    """
    import secrets
    boundary = b'----DPFBound' + secrets.token_hex(8).encode()
    crlf = b'\r\n'
    parts = []

    for name, value in fields.items():
        parts += [
            b'--' + boundary,
            ('Content-Disposition: form-data; name="%s"' % name).encode(),
            b'',
            str(value).encode('utf-8'),
        ]
    if files:
        for name, (filename, file_bytes, ctype) in files.items():
            parts += [
                b'--' + boundary,
                ('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, filename)).encode(),
                ('Content-Type: %s' % ctype).encode(),
                b'',
                file_bytes,
            ]
    parts.append(b'--' + boundary + b'--')
    body = crlf.join(parts)

    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary.decode())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_err = {}
        try:
            body_err = json.loads(e.read())
        except Exception:
            pass
        return e.code, body_err
    except Exception as exc:
        return 0, {'error': str(exc)}


class NewsPost(models.Model):
    _name        = 'news.post'
    _description = 'News Post'
    _order       = 'date desc, id desc'
    _inherit     = ['website.published.mixin']

    # ── Core fields ──────────────────────────────────────────────────────────
    name         = fields.Char(string='Title', required=True, translate=True)
    date         = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    # FIX: sanitize=False removed -> sanitize_tags=True prevents XSS while keeping formatting
    content      = fields.Html(
        string='Content', required=True, translate=True,
        sanitize=True, sanitize_tags=True, sanitize_style=False,
    )
    news_type    = fields.Selection(selection=NEWS_TYPE_SELECTION, string='News Type',
                                    required=True, default='news')
    image_ids    = fields.One2many('news.post.image', 'post_id', string='Images')
    # FIX: store=True for excerpt avoids recomputing on every list render
    excerpt      = fields.Char(string='Excerpt', compute='_compute_excerpt', store=True)
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

    # FIX: added 'content' to depends so excerpt updates when content changes
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
        # Only auto-publish on FIRST publish (not on re-publish after unpublish)
        # To re-publish manually use the "Send to Social" button / wizard
        if self.is_published and not was_published and self.social_auto_publish:
            if not self.social_log_ids.filtered(lambda l: l.status == 'sent'):
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
        caption  = '%s\n\n%s\n\n\U0001f517 %s' % (self.name, self.excerpt or '', url)
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

    # ── Telegram (direct Bot API via stdlib urllib — NO external deps) ────────
    def _publish_telegram(self, config):
        """
        FIX: was using `import requests` (external dependency not declared).
        Now uses stdlib urllib + _multipart_post helper.
        """
        token   = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            self._log_social('telegram', 'error', 'Bot token or chat_id not configured')
            return

        caption   = self._build_caption(max_len=1024)
        first_img = self.image_ids.sorted('sequence')[:1]

        try:
            if first_img and first_img.image:
                img_bytes = base64.b64decode(first_img.image)
                status, resp = _multipart_post(
                    'https://api.telegram.org/bot%s/sendPhoto' % token,
                    fields={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': ('photo.jpg', img_bytes, 'image/jpeg')},
                )
            else:
                payload = json.dumps({
                    'chat_id': chat_id,
                    'text': caption,
                    'parse_mode': 'HTML',
                }).encode('utf-8')
                req = urllib.request.Request(
                    'https://api.telegram.org/bot%s/sendMessage' % token,
                    data=payload, method='POST',
                )
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=15) as r:
                    status, resp = r.status, json.loads(r.read())

            if resp.get('ok'):
                self._log_social(
                    'telegram', 'sent',
                    'OK (message_id=%s)' % resp.get('result', {}).get('message_id', ''),
                )
            else:
                self._log_social('telegram', 'error', str(resp))
        except Exception as e:
            _logger.error('DPF News Telegram publish error: %s', e)
            self._log_social('telegram', 'error', str(e))

    # ── Facebook / Instagram / Twitter via Odoo Social Marketing module ───────
    def _publish_via_odoo_social(self, config, platform):
        """
        Use Odoo's built-in `social.post` model (module: social_media) if available.
        Falls back to logging a clear instruction if the module is not installed.
        FIX: ir.attachment now cleaned up properly if social.post.create() fails.
        """
        SocialPost = self.env.get('social.post')
        if SocialPost is None:
            self._log_social(
                platform, 'error',
                'Odoo Social Marketing app (social_media) is not installed. '
                'Install it from Apps \u2192 Social Marketing to enable %s publishing.' % platform.capitalize()
            )
            return

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
                'No connected %s account found in Social Marketing \u2192 Accounts.' % platform.capitalize()
            )
            return

        caption = self._build_caption(max_len=2000)
        vals = {
            'message':     caption,
            'account_ids': [(4, account.id)],
            'state':       'posted',
        }

        # FIX: create attachment only inside try, always clean up on failure
        attachment = None
        first_img  = self.image_ids.sorted('sequence')[:1]
        if first_img and first_img.image:
            try:
                attachment = self.env['ir.attachment'].sudo().create({
                    'name':      'news_post_%d_%s.jpg' % (self.id, platform),
                    'datas':     first_img.image,
                    'res_model': 'news.post',
                    'res_id':    self.id,
                    'mimetype':  'image/jpeg',
                })
                vals['image_ids'] = [(4, attachment.id)]
            except Exception as e:
                _logger.warning('DPF News: Could not attach image for %s: %s', platform, e)

        try:
            post = SocialPost.sudo().create(vals)
            self._log_social(platform, 'sent', 'social.post id=%d' % post.id)
        except Exception as e:
            # FIX: clean up orphan attachment if post creation failed
            if attachment:
                try:
                    attachment.sudo().unlink()
                except Exception:
                    pass
            _logger.error('DPF News social post (%s) error: %s', platform, e)
            self._log_social(platform, 'error', str(e))

    def action_open_social_wizard(self):
        """Open the social preview wizard for manual re-publish."""
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Publish to Social Media',
            'res_model': 'news.social.preview.wizard',
            'view_mode': 'form',
            'target':    'new',
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
