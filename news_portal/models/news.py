from odoo import models, fields, api
from odoo.http import request
import re


class NewsPost(models.Model):
    _name = 'news.post'
    _description = 'News Post'
    _order = 'date desc, id desc'
    _inherit = ['website.published.mixin']

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

    name = fields.Char(string='Title', required=True, translate=True)
    date = fields.Date(string='Publication Date', required=True, default=fields.Date.today)
    content = fields.Html(string='Content', required=True, translate=True, sanitize=False)
    image_ids = fields.One2many('news.post.image', 'post_id', string='Images')
    main_image = fields.Binary(
        string='Main Image',
        compute='_compute_main_image',
        store=False,
    )
    main_image_fname = fields.Char(compute='_compute_main_image', store=False)

    website_url = fields.Char(compute='_compute_website_url', store=True)

    @api.depends('name')
    def _compute_website_url(self):
        for rec in self:
            if rec.id:
                rec.website_url = '/news/%d' % rec.id
            else:
                rec.website_url = '/news'

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
            'target': 'new',   # открывается в новой вкладке
        }

    # Автоматический отрывок из content (без HTML тегов, первые 160 символов)
    excerpt = fields.Char(
        string='Excerpt',
        compute='_compute_excerpt',
        store=False,
    )

    @api.depends('content')
    def _compute_excerpt(self):
        for rec in self:
            raw = rec.content or ''
            # Убираем HTML теги
            clean = re.sub(r'<[^>]+>', ' ', raw)
            # Убираем лишние пробелы
            clean = re.sub(r'\s+', ' ', clean).strip()
            # Обрезаем до 160 символов
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
