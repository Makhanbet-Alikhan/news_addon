window.newsGallerySwitch = function (thumb) {
    var mainImg = document.getElementById('news-main-img');
    if (!mainImg || !thumb || !thumb.dataset) return;
    var oldSrc = mainImg.src;
    var newSrc = thumb.dataset.src;
    document.querySelectorAll('[data-index]').forEach(function (el) {
        el.style.border = '2px solid transparent';
    });
    thumb.style.border = '2px solid #d8b055';
    mainImg.style.opacity = '0';
    mainImg.style.transition = 'opacity 0.2s';
    setTimeout(function () {
        mainImg.src = newSrc;
        thumb.src = oldSrc;
        thumb.dataset.src = oldSrc;
        mainImg.style.opacity = '1';
    }, 200);
};
