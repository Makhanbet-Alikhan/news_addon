from odoo import models, fields, api


class DpfSocialConfig(models.Model):
    """
    Singleton config for DPF social channels.
    All platforms use direct public APIs — NO Odoo Enterprise / Social Marketing required.

    Telegram  : Bot API (stdlib urllib, no deps)
    Facebook  : Graph API v19 — Page Access Token
    Instagram : Graph API v19 — Instagram Business + Page Access Token (carousel)
    Twitter/X : API v2 + OAuth 1.0a (HMAC-SHA1, stdlib hmac)
    """
    _name        = 'dpf.social.config'
    _description = 'DPF Social Media Configuration'

    _sql_constraints = [
        ('singleton', 'CHECK(id = 1)',
         'Only one DPF Social Config record is allowed.'),
    ]

    name = fields.Char(default='DPF Social Config', readonly=True)

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_enabled   = fields.Boolean(string='Telegram Enabled', default=False)
    telegram_bot_token = fields.Char(
        string='Bot Token',
        help='Get from @BotFather. Example: 110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw',
    )
    telegram_chat_id = fields.Char(
        string='Channel / Chat ID',
        help='@channel_username  or  numeric id like -1001234567890',
    )

    # ── Facebook (Graph API) ──────────────────────────────────────────────────
    facebook_enabled      = fields.Boolean(string='Facebook Enabled', default=False)
    facebook_page_id      = fields.Char(
        string='Facebook Page ID',
        help='Numeric Page ID. Find it at facebook.com/your_page/about or in Page settings.',
    )
    facebook_page_token   = fields.Char(
        string='Page Access Token',
        help=('Long-lived Page Access Token from Meta for Developers → Graph API Explorer.\n'
              'Permissions needed: pages_manage_posts, pages_read_engagement.'),
    )

    # ── Instagram (Graph API carousel) ────────────────────────────────────────
    instagram_enabled        = fields.Boolean(string='Instagram Enabled', default=False)
    instagram_account_id     = fields.Char(
        string='Instagram Business Account ID',
        help=('Numeric ID of the Instagram Business account linked to your Facebook Page.\n'
              'Find it in Meta for Developers → Graph API Explorer: /me/accounts → instagram_business_account.'),
    )
    instagram_page_token     = fields.Char(
        string='Page Access Token (Instagram)',
        help='Same token as Facebook Page token. Needs instagram_basic, instagram_content_publish.',
    )

    # ── Twitter / X (API v2, OAuth 1.0a) ──────────────────────────────────────
    twitter_enabled              = fields.Boolean(string='Twitter/X Enabled', default=False)
    twitter_api_key              = fields.Char(string='API Key (Consumer Key)')
    twitter_api_secret           = fields.Char(string='API Secret (Consumer Secret)')
    twitter_access_token         = fields.Char(string='Access Token')
    twitter_access_token_secret  = fields.Char(string='Access Token Secret')

    # ── Singleton helper ──────────────────────────────────────────────────────
    @api.model
    def _get_config(self):
        cfg = self.search([], limit=1, order='id asc')
        if not cfg:
            cfg = self.create({'name': 'DPF Social Config'})
        return cfg
