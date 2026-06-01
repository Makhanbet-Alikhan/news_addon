from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NewsPost(models.Model):
    """
    Extends the base news.post model with email notification
    functionality for subscriber companies.
    """
    _inherit = 'news.post'

    notify_company_ids = fields.Many2many(
        comodel_name='news.company',
        relation='news_post_company_rel',
        column1='post_id',
        column2='company_id',
        string='Notify Companies',
        help='Companies that will receive an email when this news post is published.',
    )
    mail_sent = fields.Boolean(
        string='Notification Sent',
        default=False,
        copy=False,
        help='Indicates whether an email notification has been sent for this post.',
    )

    def website_publish_button(self):
        """
        Override the publish button to auto-send email
        to selected companies when the post is published.
        """
        self.ensure_one()
        was_published = self.is_published
        result = super().website_publish_button()

        # Send email only when transitioning from unpublished -> published
        if not was_published and self.is_published and self.notify_company_ids:
            self._send_news_email(self.notify_company_ids)

        return result

    def action_send_to_selected(self):
        """
        Manually send email notification to the companies
        selected in the notify_company_ids field.
        """
        self.ensure_one()
        if not self.notify_company_ids:
            raise UserError(_('Please select at least one company to notify.'))
        self._send_news_email(self.notify_company_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emails Sent'),
                'message': _('Notification sent to %d company(ies).') % len(self.notify_company_ids),
                'sticky': False,
                'type': 'success',
            },
        }

    def action_send_to_all(self):
        """
        Send email notification to ALL active subscriber companies,
        regardless of the selection in notify_company_ids.
        """
        self.ensure_one()
        all_companies = self.env['news.company'].search([('active', '=', True)])
        if not all_companies:
            raise UserError(_(
                'No active subscriber companies found. '
                'Please add companies via News Portal > Subscriber Companies.'
            ))
        self._send_news_email(all_companies)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emails Sent'),
                'message': _('Notification sent to all %d active company(ies).') % len(all_companies),
                'sticky': False,
                'type': 'success',
            },
        }

    def _send_news_email(self, companies):
        """
        Internal method to send the news notification email
        to the given companies recordset.

        :param companies: news.company recordset
        """
        template = self.env.ref(
            'dpf_news_mail.mail_template_news_notification',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_(
                'Email template not found. '
                'Please reinstall the DPF News Mail module.'
            ))

        for company in companies:
            template.with_context(company_name=company.name).send_mail(
                self.id,
                email_values={'email_to': company.email},
                force_send=True,
            )

        self.mail_sent = True
