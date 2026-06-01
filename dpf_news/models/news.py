import re
from odoo import models, fields, api


class NewsPost(models.Model):
    _name = 'news.post'
    _description = 'News Post'
    _order = 'date desc, id desc'
    _inherit = ['website.published.mixin']

    name = fields.Char(string='Title', required=True, translate=True)
    date = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    content = fields.Html(
        string='Content', required=True, translate=True,
        sanitize=True, sanitize_tags=True, sanitize_style=False,
    )
    image_ids = fields.One2many('news.post.image', 'post_id', string='Images')
    excerpt = fields.Char(string='Excerpt', compute='_compute_excerpt', store=True)
    website_url = fields.Char(compute='_compute_website_url', store=True)
    main_image = fields.Binary(compute='_compute_main_image', store=False)
    main_image_fname = fields.Char(compute='_compute_main_image', store=False)

    gallery_layout = fields.Selection([
        ('side', 'Main + thumbnails on the right'),
        ('bottom', 'Main + thumbnails below'),
    ], string='Gallery Layout', default='side')
    main_image_width = fields.Integer(string='Main Photo Width (%)', default=90)
    main_image_height = fields.Integer(string='Main Photo Height (px)', default=500)
    thumb_height = fields.Integer(string='Thumbnail Height (px)', default=120)

    @api.depends('name')
    def _compute_website_url(self):
        for rec in self:
            rec.website_url = '/news/%d' % rec.id if rec.id else '/news'

    @api.depends('image_ids', 'image_ids.image', 'image_ids.sequence')
    def _compute_main_image(self):
        for rec in self:
            first = rec.image_ids.sorted('sequence')[:1]
            rec.main_image = first.image if first else False
            rec.main_image_fname = first.name if first else False

    @api.depends('content')
    def _compute_excerpt(self):
        for rec in self:
            raw = rec.content or ''
            clean = re.sub(r'<[^>]+>', ' ', raw)
            clean = re.sub(r'\s+', ' ', clean).strip()
            rec.excerpt = (clean[:157] + '...') if len(clean) > 160 else clean

    def website_publish_button(self):
        self.ensure_one()
        self.is_published = not self.is_published
        return False

    def open_website_url(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.website_url, 'target': 'new'}


class NewsPostImage(models.Model):
    _name = 'news.post.image'
    _description = 'News Post Image'
    _order = 'sequence, id'

    post_id = fields.Many2one('news.post', string='News Post', required=True, ondelete='cascade')
    name = fields.Char(string='Caption', default='Image')
    image = fields.Binary(string='Image', required=True, attachment=True)
    image_fname = fields.Char(string='Filename')
    sequence = fields.Integer(string='Sequence', default=10)
