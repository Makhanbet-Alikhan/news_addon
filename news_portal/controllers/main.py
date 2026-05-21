from odoo import http
from odoo.http import request

POSTS_PER_PAGE = 20

class NewsPortalController(http.Controller):

    @http.route('/news', type='http', auth='public', website=True)
    def news_list(self, page=1, **kwargs):
        NewsPost = request.env['news.post'].sudo()
        page = int(page)
        PER_PAGE = 20

        total = NewsPost.search_count([('is_published', '=', True)])
        total_pages = (total + PER_PAGE - 1) // PER_PAGE
        page = max(1, min(page, total_pages))   # защита от page=9999
        offset = (page - 1) * PER_PAGE

        posts = NewsPost.search(
            [('is_published', '=', True)],
            order='date desc',
            limit=PER_PAGE,
            offset=offset
        )

        return request.render('news_portal.news_list_page', {
            'posts': posts,
            'page': page,
            'total_pages': total_pages,
            'total': total,
        })

    @http.route('/news/<int:post_id>', type='http', auth='public', website=True)
    def news_detail(self, post_id, **kwargs):
        post = request.env['news.post'].sudo().browse(post_id)
        if not post.exists() or not post.is_published:
            return request.not_found()
        images = post.image_ids.sorted('sequence')
        return request.render('news_portal.news_detail_page', {
            'post': post,
            'images': images,
            'main_image': images[0] if images else None,
            'other_images': images[1:] if len(images) > 1 else [],
            'layout': post.gallery_layout,
            'main_w': post.main_image_width,
            'thumb_h': post.thumb_height,
            'main_h': post.main_image_height,
        })