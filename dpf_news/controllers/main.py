from odoo import http
from odoo.http import request

PER_PAGE = 20


class NewsPortalController(http.Controller):

    @http.route('/news', type='http', auth='public', website=True)
    def news_list(self, page=1, **kw):
        NewsPost = request.env['news.post'].sudo()
        page = int(page)
        domain = [('is_published', '=', True)]
        total = NewsPost.search_count(domain)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * PER_PAGE
        posts = NewsPost.search(domain, order='date desc', limit=PER_PAGE, offset=offset)
        return request.render('dpf_news.news_list_page', {
            'posts': posts,
            'page': page,
            'total_pages': total_pages,
            'total': total,
        })

    @http.route('/news/<int:post_id>', type='http', auth='public', website=True)
    def news_detail(self, post_id, **kw):
        post = request.env['news.post'].sudo().browse(post_id)
        if not post.exists() or not post.is_published:
            return request.not_found()
        images = post.image_ids.sorted('sequence')
        return request.render('dpf_news.news_detail_page', {
            'post': post,
            'images': images,
            'main_image': images[0] if images else None,
            'other_images': images[1:] if len(images) > 1 else [],
            'layout': post.gallery_layout,
            'main_w': post.main_image_width,
            'thumb_h': post.thumb_height,
            'main_h': post.main_image_height,
        })
