from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NewsPost(models.Model):
    _inherit = 'news.post'

    # Many2many field - select companies to notify on publish
    notify_company_ids = fields.Many2many(
        'news.company',
        'news_post_company_rel',
        'post_id',
        'company_id',
        string='Notify Companies',
        help='Select companies to receive email notification when this news is published.',
    )
    mail_sent = fields.Boolean(string='Notification Sent', default=False, copy=False)

    def website_publish_button(self):
        """Override to send email when publishing."""
        self.ensure_one()
        was_published = self.is_published
        result = super().website_publish_button()
        # If we just published (was unpublished, now published) and companies selected
        if not was_published and self.is_published and self.notify_company_ids:
            self._send_news_email(self.notify_company_ids)
        return result

    def action_send_all_companies(self):
        """Send email notification to ALL active companies."""
        self.ensure_one()
        all_companies = self.env['news.company'].search([('active', '=', True)])
        if not all_companies:
            raise UserError(_('No active companies found. Please add companies in the News Companies menu.'))
        self._send_news_email(all_companies)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emails Sent'),
                'message': _('News notification sent to %d company(ies).') % len(all_companies),
                'sticky': False,
                'type': 'success',
            },
        }

    def action_send_selected_companies(self):
        """Send email notification to selected companies only."""
        self.ensure_one()
        if not self.notify_company_ids:
            raise UserError(_('Please select at least one company to notify.'))
        self._send_news_email(self.notify_company_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emails Sent'),
                'message': _('News notification sent to %d company(ies).') % len(self.notify_company_ids),
                'sticky': False,
                'type': 'success',
            },
        }

    def _send_news_email(self, companies):
        """Send news email to given companies recordset."""
        template = self.env.ref('dpf_news_mail.mail_template_news_notification', raise_if_not_found=False)
        if not template:
            raise UserError(_('Email template not found. Please check the module installation.'))

        for company in companies:
            template.with_context(company_name=company.name).send_mail(
                self.id,
                email_values={'email_to': company.email},
                force_send=True,
            )
        self.mail_sent = True
