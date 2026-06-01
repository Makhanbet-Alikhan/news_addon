import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
        help='Indicates whether at least one email notification has been sent for this post.',
    )
    mail_log_ids = fields.One2many(
        comodel_name='news.mail.log',
        inverse_name='post_id',
        string='Send Log',
        readonly=True,
    )
    mail_log_count = fields.Integer(
        string='Emails Sent',
        compute='_compute_mail_log_count',
    )

    def _compute_mail_log_count(self):
        for rec in self:
            rec.mail_log_count = len(rec.mail_log_ids)

    def website_publish_button(self):
        """
        Override the publish button to auto-send email
        to selected companies when the post is published.
        """
        self.ensure_one()
        was_published = self.is_published
        result = super().website_publish_button()

        # Send only when transitioning unpublished -> published
        if not was_published and self.is_published and self.notify_company_ids:
            self._send_news_email(self.notify_company_ids, trigger='publish')

        return result

    def action_send_to_selected(self):
        """
        Manually send email notification to the companies
        selected in the notify_company_ids field.
        """
        self.ensure_one()
        if not self.notify_company_ids:
            raise UserError(_('Please select at least one company to notify.'))
        sent, failed = self._send_news_email(self.notify_company_ids, trigger='manual_selected')
        return self._notification_result(sent, failed)

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
        sent, failed = self._send_news_email(all_companies, trigger='manual_all')
        return self._notification_result(sent, failed)

    def _send_news_email(self, companies, trigger='publish'):
        """
        Send the news notification email to the given companies recordset.
        Logs each attempt (success or failure) to news.mail.log.

        :param companies: news.company recordset
        :param trigger: one of 'publish', 'manual_selected', 'manual_all'
        :returns: tuple (sent_count, failed_count)
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

        # Check that outgoing mail server is configured
        mail_server = self.env['ir.mail_server'].search([], limit=1)
        if not mail_server:
            _logger.warning(
                'dpf_news_mail: No outgoing mail server configured. '
                'Go to Settings > Technical > Outgoing Mail Servers.'
            )

        sent = 0
        failed = 0
        Log = self.env['news.mail.log']

        for company in companies:
            status = 'sent'
            error_msg = False
            try:
                template.with_context(company_name=company.name).send_mail(
                    self.id,
                    email_values={'email_to': company.email},
                    force_send=True,
                )
                sent += 1
                _logger.info(
                    'dpf_news_mail: Email sent to %s <%s> for post "%s"',
                    company.name, company.email, self.name,
                )
            except Exception as e:
                status = 'failed'
                error_msg = str(e)
                failed += 1
                _logger.error(
                    'dpf_news_mail: Failed to send email to %s <%s> for post "%s": %s',
                    company.name, company.email, self.name, e,
                )

            # Write log entry regardless of success or failure
            Log.create({
                'post_id': self.id,
                'company_id': company.id,
                'company_name': company.name,
                'email_to': company.email,
                'status': status,
                'error_message': error_msg,
                'triggered_by': trigger,
            })

        if sent > 0:
            self.mail_sent = True

        return sent, failed

    def _notification_result(self, sent, failed):
        """Build a display_notification action based on send results."""
        if failed == 0:
            msg_type = 'success'
            title = _('Emails Sent')
            message = _('%d email(s) sent successfully.') % sent
        elif sent == 0:
            msg_type = 'danger'
            title = _('All Emails Failed')
            message = _('All %d email(s) failed. Check the Send Log tab for details.') % failed
        else:
            msg_type = 'warning'
            title = _('Partial Success')
            message = _('%d sent, %d failed. Check the Send Log tab for details.') % (sent, failed)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'sticky': failed > 0,
                'type': msg_type,
            },
        }
