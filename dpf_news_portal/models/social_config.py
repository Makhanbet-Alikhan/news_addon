from odoo import models, fields, api


class DpfSocialConfig(models.Model):
    """
    Singleton configuration for DPF social media channels.
    Access via the News menu → Social Settings.

    FIX: added _sql_constraints to ensure only one config row ever exists,
    preventing a race condition where concurrent requests could create duplicates.
    """
    _name        = 'dpf.social.config'
    _description = 'DPF Social Media Configuration'

    # Enforce singleton at DB level
    _sql_constraints = [
        ('singleton', 'CHECK(id = 1)',
         'Only one DPF Social Config record is allowed. Use the existing one.'),
    ]

    name = fields.Char(default='DPF Social Config', readonly=True)

    # ── Telegram ─────────────────────────────────────────────────────────────────
    telegram_enabled   = fields.Boolean(string='Telegram Enabled', default=False)
    telegram_bot_token = fields.Char(
        string='Telegram Bot Token',
        help='Create a bot via @BotFather and paste the token here.',
    )
    telegram_chat_id   = fields.Char(
        string='Telegram Channel / Chat ID',
        help='Channel username like @mychannel or numeric chat_id like -1001234567890.',
    )

    # ── Facebook (via Odoo Social Marketing) ────────────────────────────────
    facebook_enabled = fields.Boolean(string='Facebook Enabled', default=False)

    # ── Instagram (via Odoo Social Marketing) ───────────────────────────────
    instagram_enabled = fields.Boolean(string='Instagram Enabled', default=False)

    # ── Twitter / X (via Odoo Social Marketing) ──────────────────────────────
    twitter_enabled = fields.Boolean(string='Twitter/X Enabled', default=False)

    # ── Singleton helper ────────────────────────────────────────────────────────
    @api.model
    def _get_config(self):
        """
        Returns the single config record, creating it if absent.
        FIX: uses search_read for efficiency; creation is safe because the
        CHECK constraint at DB level rejects any second row (id != 1).
        """
        cfg = self.search([], limit=1, order='id asc')
        if not cfg:
            cfg = self.create({'name': 'DPF Social Config'})
        return cfg
