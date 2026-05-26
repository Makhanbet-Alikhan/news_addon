from odoo import models, fields, api


class DpfSocialConfig(models.Model):
    """
    Singleton configuration for DPF social media channels.
    Access via Settings → Technical → DPF Social Config,
    or via the News menu → Social Settings.
    """
    _name        = 'dpf.social.config'
    _description = 'DPF Social Media Configuration'

    name = fields.Char(default='DPF Social Config', readonly=True)

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_enabled   = fields.Boolean(string='Telegram Enabled', default=False)
    telegram_bot_token = fields.Char(
        string='Telegram Bot Token',
        help='Create a bot via @BotFather and paste the token here.',
    )
    telegram_chat_id   = fields.Char(
        string='Telegram Channel / Chat ID',
        help='Channel username like @mychannel or numeric chat_id like -1001234567890.',
    )

    # ── Facebook (via Odoo Social Marketing) ─────────────────────────────────
    facebook_enabled = fields.Boolean(string='Facebook Enabled', default=False)

    # ── Instagram (via Odoo Social Marketing) ────────────────────────────────
    instagram_enabled = fields.Boolean(string='Instagram Enabled', default=False)

    # ── Twitter / X (via Odoo Social Marketing) ───────────────────────────────
    twitter_enabled = fields.Boolean(string='Twitter/X Enabled', default=False)

    # ── Helper ────────────────────────────────────────────────────────────────
    @api.model
    def _get_config(self):
        cfg = self.search([], limit=1)
        if not cfg:
            cfg = self.create({'name': 'DPF Social Config'})
        return cfg
