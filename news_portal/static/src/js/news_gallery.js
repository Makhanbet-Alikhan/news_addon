/** @odoo-module **/
(function () {
    'use strict';

    function initGallery() {
        var gallery = document.getElementById('newsGallery');
        if (!gallery) return;

        var mainImg = document.getElementById('galleryMainImg');
        var thumbsEl = document.getElementById('galleryThumbs');
        if (!mainImg || !thumbsEl) return;

        function getThumbs() {
            return Array.from(thumbsEl.querySelectorAll('.np-gallery__thumb'));
        }

        function switchImage(clickedThumb) {
            var newSrc = clickedThumb.dataset.src;
            var newAlt = clickedThumb.dataset.alt || '';

            var oldSrc = mainImg.getAttribute('src');
            var oldAlt = mainImg.getAttribute('alt') || '';

            if (oldSrc === newSrc) return;

            mainImg.style.transition = 'opacity 0.18s ease';
            mainImg.style.opacity = '0';

            setTimeout(function () {
                mainImg.setAttribute('src', newSrc);
                mainImg.setAttribute('alt', newAlt);

                var thumbImg = clickedThumb.querySelector('img');
                if (thumbImg) {
                    thumbImg.setAttribute('src', oldSrc);
                    thumbImg.setAttribute('alt', oldAlt);
                }

                clickedThumb.dataset.src = oldSrc;
                clickedThumb.dataset.alt = oldAlt;

                mainImg.style.opacity = '1';
            }, 180);
        }

        function bindThumbs() {
            getThumbs().forEach(function (thumb) {
                thumb.addEventListener('click', function () {
                    switchImage(thumb);
                });
            });
        }

        bindThumbs();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGallery);
    } else {
        initGallery();
    }
})();