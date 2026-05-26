import re
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

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

TELEGRAM_MAX  = 10
FACEBOOK_MAX  = 10
INSTAGRAM_MAX = 10
TWITTER_MAX   = 4


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, zero external dependencies)
# ---------------------------------------------------------------------------

def _multipart_post(url, fields, files=None):
    """
    POST multipart/form-data.
    fields: {name: str}
    files:  {name: (filename, bytes, content_type)}
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
            b'', str(value).encode('utf-8'),
        ]
    if files:
        for name, (filename, file_bytes, ctype) in files.items():
            parts += [
                b'--' + boundary,
                ('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, filename)).encode(),
                ('Content-Type: %s' % ctype).encode(),
                b'', file_bytes,
            ]
    parts.append(b'--' + boundary + b'--')
    body = crlf.join(parts)
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary.decode())
    return _do_request(req)


def _json_post(url, payload, headers=None):
    """POST application/json. Returns (status, dict)."""
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return _do_request(req)


def _http_get(url, headers=None):
    """GET request. Returns (status, dict)."""
    req = urllib.request.Request(url, method='GET')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return _do_request(req)


def _do_request(req):
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = {}
        try:
            body = json.loads(e.read())
        except Exception:
            pass
        return e.code, body
    except Exception as exc:
        return 0, {'error': str(exc)}


# ---------------------------------------------------------------------------
# OAuth 1.0a signing helper for Twitter
# ---------------------------------------------------------------------------

def _oauth1_header(method, url, params, api_key, api_secret, token, token_secret):
    """
    Build OAuth 1.0a Authorization header (HMAC-SHA1) using only stdlib.
    """
    nonce     = uuid.uuid4().hex
    timestamp = str(int(time.time()))

    oauth_params = {
        'oauth_consumer_key':     api_key,
        'oauth_nonce':            nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp':        timestamp,
        'oauth_token':            token,
        'oauth_version':          '1.0',
    }

    all_params = {}
    all_params.update(params)
    all_params.update(oauth_params)

    sorted_params = '&'.join(
        '%s=%s' % (urllib.parse.quote(str(k), safe=''), urllib.parse.quote(str(v), safe=''))
        for k, v in sorted(all_params.items())
    )
    base_string = '&'.join([
        method.upper(),
        urllib.parse.quote(url, safe=''),
        urllib.parse.quote(sorted_params, safe=''),
    ])
    signing_key = '%s&%s' % (
        urllib.parse.quote(api_secret, safe=''),
        urllib.parse.quote(token_secret, safe=''),
    )
    signature = base64.b64encode(
        hmac.new(signing_key.encode('utf-8'), base_string.encode('utf-8'), hashlib.sha1).digest()
    ).decode()
    oauth_params['oauth_signature'] = signature

    return 'OAuth ' + ', '.join(
        '%s="%s"' % (urllib.parse.quote(k, safe=''), urllib.parse.quote(v, safe=''))
        for k, v in sorted(oauth_params.items())
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class NewsPost(models.Model):
    _name        = 'news.post'
    _description = 'News Post'
    _order       = 'date desc, id desc'
    _inherit     = ['website.published.mixin']

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

    gallery_layout    = fields.Selection([
        ('side',   'Main + thumbnails on the right'),
        ('bottom', 'Main + thumbnails below'),
    ], string='Gallery Layout', default='side')
    main_image_width  = fields.Integer(string='Main Photo Width (%)',  default=70)
    main_image_height = fields.Integer(string='Main Photo Height (px)', default=500)
    thumb_height      = fields.Integer(string='Thumbnail Height (px)',  default=120)

    social_auto_publish = fields.Boolean(
        string='Auto-publish to Social Media', default=True,
    )
    social_log_ids = fields.One2many('news.social.log', 'post_id', string='Social Publish Log')
    social_status  = fields.Selection([
        ('not_sent', 'Not sent'),
        ('partial',  'Partially sent'),
        ('sent',     'Fully sent'),
        ('error',    'Error'),
    ], string='Social Status', default='not_sent', compute='_compute_social_status', store=True)

    # ── Computes ──
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

    # ── Publish ──
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
            'type': 'ir.actions.act_window',
            'name': 'Publish to Social Media',
            'res_model': 'news.social.preview.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_post_id': self.id},
        }

    # ── Dispatcher ──
    def _social_publish_all(self):
        self.ensure_one()
        config = self.env['dpf.social.config'].sudo()._get_config()
        if not config:
            return
        if config.telegram_enabled:
            self._publish_telegram(config)
        if config.facebook_enabled:
            self._publish_facebook(config)
        if config.instagram_enabled:
            self._publish_instagram(config)
        if config.twitter_enabled:
            self._publish_twitter(config)

    # ── Helpers ──
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

    def _get_image_bytes(self, limit):
        """Return list of (raw_bytes,) tuples for each image up to limit."""
        result = []
        for img in self.image_ids.sorted('sequence')[:limit]:
            if img.image:
                try:
                    result.append(base64.b64decode(img.image))
                except Exception:
                    pass
        return result

    # =========================================================================
    # TELEGRAM  —  Bot API (100% free, no Enterprise needed)
    # =========================================================================
    def _publish_telegram(self, config):
        token   = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            self._log_social('telegram', 'error', 'Bot token or chat_id not configured')
            return

        caption  = self._build_caption(max_len=1024)
        img_list = self._get_image_bytes(TELEGRAM_MAX)

        try:
            if not img_list:
                _, resp = _json_post(
                    'https://api.telegram.org/bot%s/sendMessage' % token,
                    {'chat_id': chat_id, 'text': caption, 'parse_mode': 'HTML'},
                )
                ok_key = 'ok'
            elif len(img_list) == 1:
                _, resp = _multipart_post(
                    'https://api.telegram.org/bot%s/sendPhoto' % token,
                    fields={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': ('photo.jpg', img_list[0], 'image/jpeg')},
                )
                ok_key = 'ok'
            else:
                media = []
                files = {}
                for i, b in enumerate(img_list):
                    k = 'photo%d' % i
                    files[k] = ('photo%d.jpg' % i, b, 'image/jpeg')
                    item = {'type': 'photo', 'media': 'attach://%s' % k}
                    if i == 0:
                        item['caption']    = caption
                        item['parse_mode'] = 'HTML'
                    media.append(item)
                _, resp = _multipart_post(
                    'https://api.telegram.org/bot%s/sendMediaGroup' % token,
                    fields={'chat_id': chat_id, 'media': json.dumps(media)},
                    files=files,
                )
                ok_key = 'ok'

            if resp.get(ok_key):
                self._log_social('telegram', 'sent', 'OK (%d photo(s))' % len(img_list))
            else:
                self._log_social('telegram', 'error', str(resp))
        except Exception as e:
            _logger.error('DPF Telegram error: %s', e)
            self._log_social('telegram', 'error', str(e))

    # =========================================================================
    # FACEBOOK  —  Graph API v19  (free, Page Access Token)
    # Sends all photos as a multi-image post using attached_media
    # =========================================================================
    def _publish_facebook(self, config):
        page_id    = config.facebook_page_id
        page_token = config.facebook_page_token
        if not page_id or not page_token:
            self._log_social('facebook', 'error', 'Page ID or Page Access Token not configured')
            return

        img_list = self._get_image_bytes(FACEBOOK_MAX)
        caption  = self._build_caption(max_len=2000)
        base_url = 'https://graph.facebook.com/v19.0'

        try:
            if not img_list:
                # Text-only post
                _, resp = _json_post(
                    '%s/%s/feed' % (base_url, page_id),
                    {'message': caption, 'access_token': page_token},
                )
                if 'id' in resp:
                    self._log_social('facebook', 'sent', 'post_id=%s' % resp['id'])
                else:
                    self._log_social('facebook', 'error', str(resp))
                return

            if len(img_list) == 1:
                # Single photo post
                _, resp = _multipart_post(
                    '%s/%s/photos' % (base_url, page_id),
                    fields={'caption': caption, 'access_token': page_token},
                    files={'source': ('photo.jpg', img_list[0], 'image/jpeg')},
                )
                if 'id' in resp:
                    self._log_social('facebook', 'sent', 'photo_id=%s' % resp['id'])
                else:
                    self._log_social('facebook', 'error', str(resp))
                return

            # Multiple photos → upload each unpublished, then post together
            photo_ids = []
            for i, img_b in enumerate(img_list):
                _, r = _multipart_post(
                    '%s/%s/photos' % (base_url, page_id),
                    fields={'published': 'false', 'access_token': page_token},
                    files={'source': ('photo%d.jpg' % i, img_b, 'image/jpeg')},
                )
                if 'id' in r:
                    photo_ids.append(r['id'])
                else:
                    _logger.warning('DPF Facebook: photo %d upload failed: %s', i, r)

            if not photo_ids:
                self._log_social('facebook', 'error', 'All photo uploads failed')
                return

            attached = [{'media_fbid': pid} for pid in photo_ids]
            _, resp = _json_post(
                '%s/%s/feed' % (base_url, page_id),
                {'message': caption, 'attached_media': attached, 'access_token': page_token},
            )
            if 'id' in resp:
                self._log_social(
                    'facebook', 'sent',
                    'post_id=%s (%d photos)' % (resp['id'], len(photo_ids)),
                )
            else:
                self._log_social('facebook', 'error', str(resp))

        except Exception as e:
            _logger.error('DPF Facebook error: %s', e)
            self._log_social('facebook', 'error', str(e))

    # =========================================================================
    # INSTAGRAM  —  Graph API v19  (free, Business account + Page token)
    # Single image: create media container → publish
    # Multiple images: create item containers → carousel container → publish
    # NOTE: Instagram API requires publicly accessible image URLs.
    #       On localhost use ngrok: https://ngrok.com
    # =========================================================================
    def _publish_instagram(self, config):
        ig_id      = config.instagram_account_id
        page_token = config.instagram_page_token
        if not ig_id or not page_token:
            self._log_social('instagram', 'error', 'Instagram Account ID or Page Token not configured')
            return

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        img_list = self.image_ids.sorted('sequence')[:INSTAGRAM_MAX]
        caption  = self._build_caption(max_len=2200)
        api_base = 'https://graph.facebook.com/v19.0'

        if not img_list:
            self._log_social('instagram', 'error', 'Instagram requires at least 1 image')
            return

        try:
            def _img_url(img_rec):
                """Build public URL for the image."""
                return '%s/web/image/news.post.image/%d/image' % (base_url, img_rec.id)

            if len(img_list) == 1:
                image_url = _img_url(img_list[0])
                _, r = _json_post(
                    '%s/%s/media' % (api_base, ig_id),
                    {'image_url': image_url, 'caption': caption, 'access_token': page_token},
                )
                container_id = r.get('id')
                if not container_id:
                    self._log_social('instagram', 'error', 'Container creation failed: %s' % r)
                    return
            else:
                # Step 1: create item containers
                item_ids = []
                for img_rec in img_list:
                    image_url = _img_url(img_rec)
                    _, r = _json_post(
                        '%s/%s/media' % (api_base, ig_id),
                        {'image_url': image_url, 'is_carousel_item': 'true', 'access_token': page_token},
                    )
                    if 'id' in r:
                        item_ids.append(r['id'])
                    else:
                        _logger.warning('DPF Instagram: item container failed: %s', r)

                if not item_ids:
                    self._log_social('instagram', 'error', 'All item containers failed')
                    return

                # Step 2: create carousel container
                _, r = _json_post(
                    '%s/%s/media' % (api_base, ig_id),
                    {
                        'media_type':   'CAROUSEL',
                        'children':     ','.join(item_ids),
                        'caption':      caption,
                        'access_token': page_token,
                    },
                )
                container_id = r.get('id')
                if not container_id:
                    self._log_social('instagram', 'error', 'Carousel container failed: %s' % r)
                    return

            # Step final: publish
            _, pub = _json_post(
                '%s/%s/media_publish' % (api_base, ig_id),
                {'creation_id': container_id, 'access_token': page_token},
            )
            if 'id' in pub:
                self._log_social(
                    'instagram', 'sent',
                    'media_id=%s (%d image(s))' % (pub['id'], len(img_list)),
                )
            else:
                self._log_social('instagram', 'error', str(pub))

        except Exception as e:
            _logger.error('DPF Instagram error: %s', e)
            self._log_social('instagram', 'error', str(e))

    # =========================================================================
    # TWITTER / X  —  API v2  (free tier, OAuth 1.0a, up to 4 images)
    # Uses stdlib hmac for signature — no external OAuth libs needed
    # =========================================================================
    def _publish_twitter(self, config):
        api_key       = config.twitter_api_key
        api_secret    = config.twitter_api_secret
        access_token  = config.twitter_access_token
        token_secret  = config.twitter_access_token_secret

        if not all([api_key, api_secret, access_token, token_secret]):
            self._log_social('twitter', 'error', 'Twitter API credentials not fully configured')
            return

        caption  = self._build_caption(max_len=280)
        img_list = self._get_image_bytes(TWITTER_MAX)

        try:
            media_ids = []
            for i, img_b in enumerate(img_list):
                # Upload via v1.1 media/upload (v2 doesn't have its own upload endpoint)
                upload_url = 'https://upload.twitter.com/1.1/media/upload.json'
                auth_hdr = _oauth1_header(
                    'POST', upload_url, {},
                    api_key, api_secret, access_token, token_secret,
                )
                _, r = _multipart_post(
                    upload_url,
                    fields={'Authorization': auth_hdr},  # passed as header below
                    files={'media': ('photo%d.jpg' % i, img_b, 'image/jpeg')},
                )
                # Re-do with proper header
                import secrets as _sec
                boundary = b'----TwBound' + _sec.token_hex(4).encode()
                body = (b'--' + boundary + b'\r\n'
                        b'Content-Disposition: form-data; name="media"; filename="photo.jpg"\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        img_b + b'\r\n' + b'--' + boundary + b'--')
                req = urllib.request.Request(upload_url, data=body, method='POST')
                req.add_header('Authorization', auth_hdr)
                req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary.decode())
                _, r = _do_request(req)
                mid = r.get('media_id_string')
                if mid:
                    media_ids.append(mid)
                else:
                    _logger.warning('DPF Twitter media upload %d failed: %s', i, r)

            # Post tweet via API v2
            tweet_url = 'https://api.twitter.com/2/tweets'
            tweet_payload = {'text': caption}
            if media_ids:
                tweet_payload['media'] = {'media_ids': media_ids}

            auth_hdr = _oauth1_header(
                'POST', tweet_url, {},
                api_key, api_secret, access_token, token_secret,
            )
            _, resp = _json_post(tweet_url, tweet_payload, headers={'Authorization': auth_hdr})

            if resp.get('data', {}).get('id'):
                self._log_social(
                    'twitter', 'sent',
                    'tweet_id=%s (%d media)' % (resp['data']['id'], len(media_ids)),
                )
            else:
                self._log_social('twitter', 'error', str(resp))

        except Exception as e:
            _logger.error('DPF Twitter error: %s', e)
            self._log_social('twitter', 'error', str(e))


class NewsPostImage(models.Model):
    _name        = 'news.post.image'
    _description = 'News Post Image'
    _order       = 'sequence, id'

    post_id     = fields.Many2one('news.post', string='News Post', required=True, ondelete='cascade')
    name        = fields.Char(string='Caption', default='Image')
    image       = fields.Binary(string='Image', required=True, attachment=True)
    image_fname = fields.Char(string='Filename')
    sequence    = fields.Integer(string='Sequence', default=10)
