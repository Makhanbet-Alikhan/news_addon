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

TELEGRAM_MAX = 10
FACEBOOK_MAX = 10
INSTAGRAM_MAX = 10
TWITTER_MAX = 4


def _multipart_post(url, fields, files=None):
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
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
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


def _oauth1_header(method, url, params, api_key, api_secret, token, token_secret):
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))
    oauth_params = {
        'oauth_consumer_key': api_key,
        'oauth_nonce': nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': timestamp,
        'oauth_token': token,
        'oauth_version': '1.0',
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


class NewsPost(models.Model):
    _inherit = 'news.post'

    social_auto_publish = fields.Boolean(string='Auto-publish to Social Media', default=True)
    social_log_ids = fields.One2many('news.social.log', 'post_id', string='Social Publish Log')
    social_status = fields.Selection([
        ('not_sent', 'Not sent'),
        ('partial', 'Partially sent'),
        ('sent', 'Fully sent'),
        ('error', 'Error'),
    ], string='Social Status', default='not_sent', compute='_compute_social_status', store=True)

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

    def website_publish_button(self):
        self.ensure_one()
        was_published = self.is_published
        result = super().website_publish_button()
        if self.is_published and not was_published and self.social_auto_publish:
            if not self.social_log_ids.filtered(lambda l: l.status == 'sent'):
                self._social_publish_all()
        return result

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

    def _clean_html(self, html):
        """Strip HTML tags and clean up HTML entities from content."""
        import re, html as _html
        text = re.sub(r'<br\s*/?>', '\n', html or '')
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = _html.unescape(text)           # &nbsp; &amp; &lt; etc → plain text
        text = re.sub(r'\u00a0', ' ', text)  # non-breaking space
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _build_caption(self, max_len=2000):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        url = base_url.rstrip('/') + self.website_url
        caption = '%s\n\n%s\n\n\U0001f517 %s' % (self.name, self.excerpt or '', url)
        return caption[:max_len - 3] + '...' if len(caption) > max_len else caption

    def _build_telegram_message(self):
        import re
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        url = base_url.rstrip('/') + self.website_url

        full_text = self._clean_html(self.content or '')

        sentences = re.split(r'(?<=[.!?\u0021\u003f])\s+', full_text)
        preview = ''
        truncated = False
        for s in sentences:
            if len(preview) + len(s) + 1 <= 600:
                preview += (' ' if preview else '') + s
            else:
                truncated = True
                break
        if not preview:
            preview = full_text[:600]
            truncated = len(full_text) > 600

        if truncated:
            preview = preview.rstrip('.') + '...'

        def _e(s):
            # Escape only &, < , > — leave everything else as-is
            return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        text = (
            '<b>%s</b>\n'
            '\U0001f4c5 %s\n\n'
            '%s'
        ) % (_e(self.name), self.date.strftime('%d.%m.%Y'), _e(preview))

        return text, url
    def _log_social(self, channel, status, message=''):
        self.env['news.social.log'].sudo().create({
            'post_id': self.id,
            'channel': channel,
            'status':  status,
            'message': message or '',
        })

    def _get_image_bytes(self, limit):
        result = []
        for img in self.image_ids.sorted('sequence')[:limit]:
            if img.image:
                try:
                    result.append(base64.b64decode(img.image))
                except Exception:
                    pass
        return result

    def _publish_telegram(self, config):
        token = config.telegram_bot_token
        chat_id = config.telegram_chat_id
        if not token or not chat_id:
            self._log_social('telegram', 'error', 'Bot token or chat_id not configured')
            return

        text, url = self._build_telegram_message()
        img_list = self._get_image_bytes(TELEGRAM_MAX)

        # reply_markup как dict — _json_post сам превратит его в JSON
        reply_markup = {
            'inline_keyboard': [[{'text': '\U0001f517 Читать полностью', 'url': url}]]
        }

        def _send_text_msg():
            # Telegram rejects localhost/private URLs in inline_keyboard buttons
            is_public_url = url.startswith('http') and 'localhost' not in url and '127.0.0.1' not in url
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            if is_public_url:
                payload['reply_markup'] = reply_markup
            else:
                # Fallback: append URL as plain text inside message
                payload['text'] = text + '\n\n\U0001f517 ' + url
            status, r = _json_post(
                'https://api.telegram.org/bot%s/sendMessage' % token,
                payload,
            )
            _logger.info('DPF Telegram sendMessage -> status=%s resp=%s', status, r)
            return r

        try:
            if not img_list:
                resp = _send_text_msg()
            elif len(img_list) == 1:
                # Send photo as multipart — fields dict, no reply_markup (not supported in caption)
                s, pr = _multipart_post(
                    'https://api.telegram.org/bot%s/sendPhoto' % token,
                    fields={'chat_id': chat_id},
                    files={'photo': ('photo.jpg', img_list[0], 'image/jpeg')},
                )
                _logger.info('DPF Telegram sendPhoto -> status=%s resp=%s', s, pr)
                resp = _send_text_msg()
            else:
                media_list = []
                files = {}
                for i, b in enumerate(img_list):
                    k = 'photo%d' % i
                    files[k] = ('photo%d.jpg' % i, b, 'image/jpeg')
                    media_list.append({'type': 'photo', 'media': 'attach://%s' % k})
                s, pr = _multipart_post(
                    'https://api.telegram.org/bot%s/sendMediaGroup' % token,
                    fields={'chat_id': chat_id, 'media': json.dumps(media_list)},
                    files=files,
                )
                _logger.info('DPF Telegram sendMediaGroup -> status=%s resp=%s', s, pr)
                resp = _send_text_msg()

            if resp.get('ok'):
                self._log_social('telegram', 'sent', 'OK (%d photo(s))' % len(img_list))
            else:
                self._log_social('telegram', 'error', str(resp))
        except Exception as e:
            _logger.error('DPF Telegram error: %s', e)
            self._log_social('telegram', 'error', str(e))

    def _publish_facebook(self, config):
        page_id = config.facebook_page_id
        page_token = config.facebook_page_token
        if not page_id or not page_token:
            self._log_social('facebook', 'error', 'Page ID or Page Access Token not configured')
            return
        img_list = self._get_image_bytes(FACEBOOK_MAX)
        caption = self._build_caption(max_len=2000)
        base_url = 'https://graph.facebook.com/v19.0'
        try:
            if not img_list:
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
            photo_ids = []
            for i, img_b in enumerate(img_list):
                _, r = _multipart_post(
                    '%s/%s/photos' % (base_url, page_id),
                    fields={'published': 'false', 'access_token': page_token},
                    files={'source': ('photo%d.jpg' % i, img_b, 'image/jpeg')},
                )
                if 'id' in r:
                    photo_ids.append(r['id'])
            if not photo_ids:
                self._log_social('facebook', 'error', 'All photo uploads failed')
                return
            _, resp = _json_post(
                '%s/%s/feed' % (base_url, page_id),
                {'message': caption, 'attached_media': [{'media_fbid': pid} for pid in photo_ids], 'access_token': page_token},
            )
            if 'id' in resp:
                self._log_social('facebook', 'sent', 'post_id=%s (%d photos)' % (resp['id'], len(photo_ids)))
            else:
                self._log_social('facebook', 'error', str(resp))
        except Exception as e:
            _logger.error('DPF Facebook error: %s', e)
            self._log_social('facebook', 'error', str(e))

    def _publish_instagram(self, config):
        ig_id = config.instagram_account_id
        page_token = config.instagram_page_token
        if not ig_id or not page_token:
            self._log_social('instagram', 'error', 'Instagram Account ID or Page Token not configured')
            return
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        img_list = self.image_ids.sorted('sequence')[:INSTAGRAM_MAX]
        caption = self._build_caption(max_len=2200)
        api_base = 'https://graph.facebook.com/v19.0'
        if not img_list:
            self._log_social('instagram', 'error', 'Instagram requires at least 1 image')
            return
        try:
            def _img_url(img_rec):
                return '%s/web/image/news.post.image/%d/image' % (base_url, img_rec.id)

            if len(img_list) == 1:
                _, r = _json_post(
                    '%s/%s/media' % (api_base, ig_id),
                    {'image_url': _img_url(img_list[0]), 'caption': caption, 'access_token': page_token},
                )
                container_id = r.get('id')
                if not container_id:
                    self._log_social('instagram', 'error', 'Container creation failed: %s' % r)
                    return
            else:
                item_ids = []
                for img_rec in img_list:
                    _, r = _json_post(
                        '%s/%s/media' % (api_base, ig_id),
                        {'image_url': _img_url(img_rec), 'is_carousel_item': 'true', 'access_token': page_token},
                    )
                    if 'id' in r:
                        item_ids.append(r['id'])
                if not item_ids:
                    self._log_social('instagram', 'error', 'All item containers failed')
                    return
                _, r = _json_post(
                    '%s/%s/media' % (api_base, ig_id),
                    {'media_type': 'CAROUSEL', 'children': ','.join(item_ids), 'caption': caption, 'access_token': page_token},
                )
                container_id = r.get('id')
                if not container_id:
                    self._log_social('instagram', 'error', 'Carousel container failed: %s' % r)
                    return
            _, pub = _json_post(
                '%s/%s/media_publish' % (api_base, ig_id),
                {'creation_id': container_id, 'access_token': page_token},
            )
            if 'id' in pub:
                self._log_social('instagram', 'sent', 'media_id=%s (%d image(s))' % (pub['id'], len(img_list)))
            else:
                self._log_social('instagram', 'error', str(pub))
        except Exception as e:
            _logger.error('DPF Instagram error: %s', e)
            self._log_social('instagram', 'error', str(e))

    def _publish_twitter(self, config):
        api_key = config.twitter_api_key
        api_secret = config.twitter_api_secret
        access_token = config.twitter_access_token
        token_secret = config.twitter_access_token_secret
        if not all([api_key, api_secret, access_token, token_secret]):
            self._log_social('twitter', 'error', 'Twitter API credentials not fully configured')
            return
        caption = self._build_caption(max_len=280)
        img_list = self._get_image_bytes(TWITTER_MAX)
        try:
            media_ids = []
            for i, img_b in enumerate(img_list):
                upload_url = 'https://upload.twitter.com/1.1/media/upload.json'
                auth_hdr = _oauth1_header('POST', upload_url, {}, api_key, api_secret, access_token, token_secret)
                import secrets as _sec
                boundary = b'----TwBound' + _sec.token_hex(4).encode()
                body = (
                    b'--' + boundary + b'\r\n'
                    b'Content-Disposition: form-data; name="media"; filename="photo.jpg"\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + img_b + b'\r\n'
                    + b'--' + boundary + b'--'
                )
                req = urllib.request.Request(upload_url, data=body, method='POST')
                req.add_header('Authorization', auth_hdr)
                req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary.decode())
                _, r = _do_request(req)
                mid = r.get('media_id_string')
                if mid:
                    media_ids.append(mid)
                else:
                    _logger.warning('DPF Twitter media upload %d failed: %s', i, r)
            tweet_url = 'https://api.twitter.com/2/tweets'
            tweet_payload = {'text': caption}
            if media_ids:
                tweet_payload['media'] = {'media_ids': media_ids}
            auth_hdr = _oauth1_header('POST', tweet_url, {}, api_key, api_secret, access_token, token_secret)
            _, resp = _json_post(tweet_url, tweet_payload, headers={'Authorization': auth_hdr})
            if resp.get('data', {}).get('id'):
                self._log_social('twitter', 'sent', 'tweet_id=%s (%d media)' % (resp['data']['id'], len(media_ids)))
            else:
                self._log_social('twitter', 'error', str(resp))
        except Exception as e:
            _logger.error('DPF Twitter error: %s', e)
            self._log_social('twitter', 'error', str(e))
