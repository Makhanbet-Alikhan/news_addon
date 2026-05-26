import re
import base64
import json
import logging
import urllib.request
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

# Max photos per platform
TELEGRAM_MAX_PHOTOS  = 10   # Bot API hard limit for sendMediaGroup
FACEBOOK_MAX_PHOTOS  = 10   # Graph API practical limit
INSTAGRAM_MAX_PHOTOS = 10   # Carousel limit
TWITTER_MAX_PHOTOS   = 4    # Twitter API v2 hard limit


# ---------------------------------------------------------------------------
# Lightweight multipart helper — no external dependencies
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
        with urllib.request.urlopen(req, timeout=30) as resp:
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


def _json_post(url, payload_dict):
    """POST application/json using stdlib urllib. Returns (status, dict)."""
    payload = json.dumps(payload_dict).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class NewsPost(models.Model):
    _name        = 'news.post'
    _description = 'News Post'
    _order       = 'date desc, id desc'
    _inherit     = ['website.published.mixin']

    # ── Core fields ──────────────────────────────────────────────────────────
    name    = fields.Char(string='Title', required=True, translate=True)
    date    = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    content = fields.Html(
        string='Content', required=True, translate=True,
        sanitize=True, sanitize_tags=True, sanitize_style=False,
    )
    news_type = fields.Selection(
        selection=NEWS_TYPE_SELECTION, string='News Type', required=True, default='news',
    )
    image_ids        = fields.One2many('news.post.image', 'post_id', string='Images')
    excerpt          = fields.Char(string='Excerpt', compute='_compute_excerpt', store=True)
    website_url      = fields.Char(compute='_compute_website_url', store=True)
    main_image       = fields.Binary(compute='_compute_main_image', store=False)
    main_image_fname = fields.Char(compute='_compute_main_image', store=False)

    # ── Gallery settings ─────────────────────────────────────────────────────
    gallery_layout    = fields.Selection([
        ('side',   'Main + thumbnails on the right'),
        ('bottom', 'Main + thumbnails below'),
    ], string='Gallery Layout', default='side')
    main_image_width  = fields.Integer(string='Main Photo Width (%)',  default=70)
    main_image_height = fields.Integer(string='Main Photo Height (px)', default=500)
    thumb_height      = fields.Integer(string='Thumbnail Height (px)',  default=120)

    # ── Social publishing ─────────────────────────────────────────────────────
    social_auto_publish = fields.Boolean(
        string='Auto-publish to Social Media', default=True,
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

    # ── Publish button ────────────────────────────────────────────────────────
    def website_publish_button(self):
        self.ensure_one()
        was_published = self.is_published
        self.is_published = not self.is_published
        if self.is_published and not was_published and self.social_auto_publish:
            if not self.social_log_ids.filtered(lambda l: l.status == 'sent'):
                self._social_publish_all()
        return False

    def open_website_url(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.website_url, 'target': 'new'}

    def action_open_social_wizard(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      'Publish to Social Media',
            'res_model': 'news.social.preview.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_post_id': self.id},
        }

    # ── Social dispatcher ─────────────────────────────────────────────────────
    def _social_publish_all(self):
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

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _build_caption(self, max_len=2000):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        url      = base_url.rstrip('/') + self.website_url
        caption  = '%s\n\n%s\n\n\U0001f517 %s' % (self.name, self.excerpt or '', url)
        return caption[:max_len - 3] + '...' if len(caption) > max_len else caption

    def _log_social(self, channel, status, message=''):
        self.env['news.social.log'].sudo().create({
            'post_id': self.id,
            'channel': channel,
            'status':  status,
            'message': message or '',
        })

    def _get_image_bytes(self, limit=10):
        """Return list of raw bytes for sorted images, up to `limit`."""
        result = []
        for img in self.image_ids.sorted('sequence')[:limit]:
            if img.image:
                try:
                    result.append(base64.b64decode(img.image))
                except Exception:
                    pass
        return result

    # =========================================================================
    # Telegram — sendPhoto (1 image) / sendMediaGroup (2-10 images)
    # =========================================================================
    def _publish_telegram(self, config):
        token   = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            self._log_social('telegram', 'error', 'Bot token or chat_id not configured')
            return

        caption    = self._build_caption(max_len=1024)
        img_bytes_list = self._get_image_bytes(limit=TELEGRAM_MAX_PHOTOS)

        try:
            # ── No images → plain text message ───────────────────────────────
            if not img_bytes_list:
                _, resp = _json_post(
                    'https://api.telegram.org/bot%s/sendMessage' % token,
                    {'chat_id': chat_id, 'text': caption, 'parse_mode': 'HTML'},
                )
                if resp.get('ok'):
                    self._log_social('telegram', 'sent', 'OK (text message)')
                else:
                    self._log_social('telegram', 'error', str(resp))
                return

            # ── 1 image → sendPhoto ───────────────────────────────────────────
            if len(img_bytes_list) == 1:
                _, resp = _multipart_post(
                    'https://api.telegram.org/bot%s/sendPhoto' % token,
                    fields={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': ('photo.jpg', img_bytes_list[0], 'image/jpeg')},
                )
                if resp.get('ok'):
                    mid = resp.get('result', {}).get('message_id', '')
                    self._log_social('telegram', 'sent', 'OK (1 photo, message_id=%s)' % mid)
                else:
                    self._log_social('telegram', 'error', str(resp))
                return

            # ── 2-10 images → sendMediaGroup (album) ─────────────────────────
            media = []
            files = {}
            for idx, img_b in enumerate(img_bytes_list):
                key = 'photo%d' % idx
                files[key] = ('photo%d.jpg' % idx, img_b, 'image/jpeg')
                item = {'type': 'photo', 'media': 'attach://%s' % key}
                if idx == 0:                          # caption only on first item
                    item['caption']    = caption
                    item['parse_mode'] = 'HTML'
                media.append(item)

            _, resp = _multipart_post(
                'https://api.telegram.org/bot%s/sendMediaGroup' % token,
                fields={'chat_id': chat_id, 'media': json.dumps(media)},
                files=files,
            )
            if resp.get('ok'):
                self._log_social(
                    'telegram', 'sent',
                    'OK (album of %d photos)' % len(img_bytes_list),
                )
            else:
                self._log_social('telegram', 'error', str(resp))

        except Exception as e:
            _logger.error('DPF News Telegram publish error: %s', e)
            self._log_social('telegram', 'error', str(e))

    # =========================================================================
    # Facebook / Instagram / Twitter — via Odoo Social Marketing module
    # All available images are attached as ir.attachment records.
    # =========================================================================
    def _publish_via_odoo_social(self, config, platform):
        SocialPost = self.env.get('social.post')
        if SocialPost is None:
            self._log_social(
                platform, 'error',
                'Odoo Social Marketing app (social_media) is not installed. '
                'Install it from Apps → Social Marketing to enable %s publishing.' % platform.capitalize(),
            )
            return

        media_type_map = {'facebook': 'facebook', 'instagram': 'instagram', 'twitter': 'twitter'}
        account = self.env['social.account'].sudo().search([
            ('media_type', '=', media_type_map.get(platform, platform)),
            ('has_account_link', '=', True),
        ], limit=1)

        if not account:
            self._log_social(
                platform, 'error',
                'No connected %s account found in Social Marketing → Accounts.' % platform.capitalize(),
            )
            return

        # Limit per platform
        limits = {
            'facebook':  FACEBOOK_MAX_PHOTOS,
            'instagram': INSTAGRAM_MAX_PHOTOS,
            'twitter':   TWITTER_MAX_PHOTOS,
        }
        max_photos = limits.get(platform, 4)
        images     = self.image_ids.sorted('sequence')[:max_photos]

        caption = self._build_caption(max_len=2000)
        vals = {
            'message':     caption,
            'account_ids': [(4, account.id)],
            'state':       'posted',
        }

        # Create one ir.attachment per image and link them all to social.post
        attachments = []
        for idx, img in enumerate(images):
            if not img.image:
                continue
            try:
                att = self.env['ir.attachment'].sudo().create({
                    'name':      'news_%d_%s_%d.jpg' % (self.id, platform, idx),
                    'datas':     img.image,
                    'res_model': 'news.post',
                    'res_id':    self.id,
                    'mimetype':  'image/jpeg',
                })
                attachments.append(att)
            except Exception as e:
                _logger.warning('DPF News: Could not create attachment %d for %s: %s', idx, platform, e)

        if attachments:
            vals['image_ids'] = [(4, att.id) for att in attachments]

        try:
            post = SocialPost.sudo().create(vals)
            self._log_social(
                platform, 'sent',
                'social.post id=%d (%d image(s))' % (post.id, len(attachments)),
            )
        except Exception as e:
            # Clean up orphan attachments on failure
            for att in attachments:
                try:
                    att.sudo().unlink()
                except Exception:
                    pass
            _logger.error('DPF News social post (%s) error: %s', platform, e)
            self._log_social(platform, 'error', str(e))


class NewsPostImage(models.Model):
    _name        = 'news.post.image'
    _description = 'News Post Image'
    _order       = 'sequence, id'

    post_id     = fields.Many2one('news.post', string='News Post', required=True, ondelete='cascade')
    name        = fields.Char(string='Caption', default='Image')
    image       = fields.Binary(string='Image', required=True, attachment=True)
    image_fname = fields.Char(string='Filename')
    sequence    = fields.Integer(string='Sequence', default=10)
