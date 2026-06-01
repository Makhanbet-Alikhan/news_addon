from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_open_dpf_social_config(self):
        config = self.env['dpf.social.config'].sudo()._get_config()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Social Media Settings',
            'res_model': 'dpf.social.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
            'context': {'create': False, 'delete': False},
        }
