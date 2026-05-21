from odoo import models, fields, api
import re


NEWS_TYPE_SELECTION = [
    ('news', 'News'),
    ('announcements', 'Announcements'),
    ('pre_releases', 'Pre-releases'),
]

# Maps news_type value -> website URL prefix
TYPE_URL = {
    'news': '/news',
    'announcements': '/announcements',
    'pre_releases': '/pre-releases',
}


class NewsPost(models.Model):
    _name = 'news.post'
    _description = 'News Post'
    _order = 'date desc, id desc'
    _inherit = ['website.published.mixin']

    # ── Gallery settings ──────────────────────────────────────
    gallery_layout = fields.Selection([
        ('side', 'Основное + миниатюры справа'),
        ('bottom', 'Основное + миниатюры снизу'),
    ], string='Расположение галереи', default='side')

    main_image_width = fields.Integer(
        string='Ширина основного фото (%)',
        default=70,
        help='Ширина главной картинки в процентах (например 70)'
    )

    thumb_size = fields.Integer(
        string='Ширина миниатюр (%)',
        default=30,
        help='Ширина блока миниатюр в процентах (например 30)'
    )

    main_image_height = fields.Integer(
        string='Высота основного фото (px)',
        default=500,
        help='Высота главной картинки в пикселях (используется в режиме "снизу")'
    )

    thumb_height = fields.Integer(
        string='Высота миниатюр (px)',
        default=120,
        help='Высота миниатюр в пикселях (используется в режиме "снизу")'
    )

    # ── Main fields ───────────────────────────────────────────
    name = fields.Char(string='Title', required=True, translate=True)
    date = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    content = fields.Html(string='Content', required=True, translate=True, sanitize=False)

    news_type = fields.Selection(
        selection=NEWS_TYPE_SELECTION,
        string='News Type',
        required=True,
        default='news',
        help='Type determines which section this post appears in on the website.'
    )

    image_ids = fields.One2many('news.post.image', 'post_id', string='Images')
    main_image = fields.Binary(
        string='Main Image',
        compute='_compute_main_image',
        store=False,
    )
    main_image_fname = fields.Char(compute='_compute_main_image', store=False)

    website_url = fields.Char(compute='_compute_website_url', store=True)

    @api.depends('name', 'news_type')
    def _compute_website_url(self):
        for rec in self:
            base = TYPE_URL.get(rec.news_type or 'news', '/news')
            if rec.id:
                rec.website_url = '%s/%d' % (base, rec.id)
            else:
                rec.website_url = base

    @api.depends('image_ids', 'image_ids.image', 'image_ids.sequence')
    def _compute_main_image(self):
        for rec in self:
            first = rec.image_ids.sorted('sequence')[:1]
            rec.main_image = first.image if first else False
            rec.main_image_fname = first.name if first else False

    def website_publish_button(self):
        self.ensure_one()
        self.is_published = not self.is_published
        return False

    def open_website_url(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.website_url,
            'target': 'new',
        }

    # ── Excerpt ───────────────────────────────────────────────
    excerpt = fields.Char(
        string='Excerpt',
        compute='_compute_excerpt',
        store=False,
    )

    @api.depends('content')
    def _compute_excerpt(self):
        for rec in self:
            raw = rec.content or ''
            clean = re.sub(r'<[^>]+>', ' ', raw)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) > 160:
                clean = clean[:157] + '...'
            rec.excerpt = clean


class NewsPostImage(models.Model):
    _name = 'news.post.image'
    _description = 'News Post Image'
    _order = 'sequence, id'

    post_id = fields.Many2one('news.post', string='News Post', required=True, ondelete='cascade')
    name = fields.Char(string='Caption', default='Image')
    image = fields.Binary(string='Image', required=True, attachment=True)
    image_fname = fields.Char(string='Filename')
    sequence = fields.Integer(string='Sequence', default=10)
