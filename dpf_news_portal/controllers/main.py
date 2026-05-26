from odoo import http
from odoo.http import request

PER_PAGE = 20


def _get_posts_context(news_type, page):
    NewsPost    = request.env['news.post'].sudo()
    page        = int(page)
    domain      = [('is_published', '=', True), ('news_type', '=', news_type)]
    total       = NewsPost.search_count(domain)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page        = max(1, min(page, total_pages))
    offset      = (page - 1) * PER_PAGE
    posts       = NewsPost.search(domain, order='date desc', limit=PER_PAGE, offset=offset)
    return posts, page, total_pages, total


class NewsPortalController(http.Controller):

    # ── News ──────────────────────────────────────────────────────────────────
    @http.route('/news', type='http', auth='public', website=True)
    def news_list(self, page=1, **kw):
        posts, page, total_pages, total = _get_posts_context('news', page)
        return request.render('dpf_news_portal.news_list_page', {
            'posts': posts, 'page': page, 'total_pages': total_pages,
            'total': total, 'news_type': 'news', 'section_url': '/news',
        })

    @http.route('/news/<int:post_id>', type='http', auth='public', website=True)
    def news_detail(self, post_id, **kw):
        return self._render_detail(post_id, 'news', '/news')

    # ── Announcements ─────────────────────────────────────────────────────────
    @http.route('/announcements', type='http', auth='public', website=True)
    def announcements_list(self, page=1, **kw):
        posts, page, total_pages, total = _get_posts_context('announcements', page)
        return request.render('dpf_news_portal.news_list_page', {
            'posts': posts, 'page': page, 'total_pages': total_pages,
            'total': total, 'news_type': 'announcements', 'section_url': '/announcements',
        })

    @http.route('/announcements/<int:post_id>', type='http', auth='public', website=True)
    def announcements_detail(self, post_id, **kw):
        return self._render_detail(post_id, 'announcements', '/announcements')

    # ── Pre-releases ──────────────────────────────────────────────────────────
    @http.route('/pre-releases', type='http', auth='public', website=True)
    def pre_releases_list(self, page=1, **kw):
        posts, page, total_pages, total = _get_posts_context('pre_releases', page)
        return request.render('dpf_news_portal.news_list_page', {
            'posts': posts, 'page': page, 'total_pages': total_pages,
            'total': total, 'news_type': 'pre_releases', 'section_url': '/pre-releases',
        })

    @http.route('/pre-releases/<int:post_id>', type='http', auth='public', website=True)
    def pre_releases_detail(self, post_id, **kw):
        return self._render_detail(post_id, 'pre_releases', '/pre-releases')

    # ── Helper ────────────────────────────────────────────────────────────────
    def _render_detail(self, post_id, expected_type, section_url):
        post = request.env['news.post'].sudo().browse(post_id)
        if not post.exists() or not post.is_published or post.news_type != expected_type:
            return request.not_found()
        images = post.image_ids.sorted('sequence')
        return request.render('dpf_news_portal.news_detail_page', {
            'post':        post,
            'images':      images,
            'main_image':  images[0] if images else None,
            'other_images': images[1:] if len(images) > 1 else [],
            'layout':      post.gallery_layout,
            'main_w':      post.main_image_width,
            'thumb_h':     post.thumb_height,
            'main_h':      post.main_image_height,
            'section_url': section_url,
            'news_type':   expected_type,
        })
