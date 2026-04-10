/**
 * gallery.js — Event gallery page
 *
 * Masonry layout with lazy loading and lightbox.
 * Auto-refreshes every 30 seconds.
 */

(function () {
    var REFRESH_INTERVAL = 30000;
    var allPhotos = [];
    var currentIndex = -1;
    var lightboxOverlay = null;

    function init() {
        loadGallery();
        setInterval(loadGallery, REFRESH_INTERVAL);
        loadEventName();

        // Global keyboard handler for lightbox
        document.addEventListener('keydown', function (e) {
            if (!lightboxOverlay) return;
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigateLightbox(-1);
            if (e.key === 'ArrowRight') navigateLightbox(1);
        });
    }

    async function loadEventName() {
        try {
            var res = await fetch('/api/admin/config');
            var data = await res.json();
            var name = data.sharing && data.sharing.event_name;
            if (name) {
                document.getElementById('event-name').textContent = name;
                document.title = name + ' - Photo Gallery';
            }
        } catch (e) {
            // Use default title
        }
    }

    async function loadGallery() {
        try {
            var res = await fetch('/api/gallery/?limit=100');
            var data = await res.json();
            allPhotos = data.photos || [];
            renderMasonry(allPhotos);
        } catch (e) {
            console.error('[gallery] fetch failed:', e);
        }
    }

    function getColumnCount() {
        var w = window.innerWidth;
        if (w > 1000) return 4;
        if (w > 700) return 3;
        return 2;
    }

    function renderMasonry(photos) {
        var grid = document.getElementById('gallery-grid');
        var empty = document.getElementById('gallery-empty');
        var countEl = document.getElementById('photo-count');

        if (photos.length === 0) {
            grid.innerHTML = '';
            empty.style.display = '';
            countEl.textContent = '';
            return;
        }

        empty.style.display = 'none';
        countEl.textContent = photos.length + ' photo' + (photos.length !== 1 ? 's' : '');

        var columns = getColumnCount();
        var columnPhotos = [];
        var columnHeights = [];
        for (var c = 0; c < columns; c++) {
            columnPhotos.push([]);
            columnHeights.push(0);
        }

        // Distribute to shortest column
        for (var i = 0; i < photos.length; i++) {
            var shortest = 0;
            for (var j = 1; j < columns; j++) {
                if (columnHeights[j] < columnHeights[shortest]) shortest = j;
            }
            columnPhotos[shortest].push({ photo: photos[i], index: i });
            columnHeights[shortest] += 1;
        }

        var html = '<div class="masonry-grid">';
        for (var c = 0; c < columns; c++) {
            html += '<div class="masonry-column">';
            for (var k = 0; k < columnPhotos[c].length; k++) {
                var item = columnPhotos[c][k];
                html += '<div class="gallery-card" data-index="' + item.index + '">';
                var isGif = item.photo.photo_path && item.photo.photo_path.endsWith('.gif');
                html += '<img data-src="/api/gallery/' + item.photo.id + (isGif ? '' : '/thumbnail') + '" alt="Photo">';
                html += '</div>';
            }
            html += '</div>';
        }
        html += '</div>';
        grid.innerHTML = html;

        // Lazy load with IntersectionObserver
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var img = entry.target;
                    img.src = img.dataset.src;
                    img.onload = function () { img.classList.add('loaded'); };
                    observer.unobserve(img);
                }
            });
        }, { rootMargin: '200px' });

        grid.querySelectorAll('.gallery-card img[data-src]').forEach(function (img) {
            observer.observe(img);
        });

        // Click to open lightbox
        grid.querySelectorAll('.gallery-card').forEach(function (card) {
            card.addEventListener('click', function () {
                var idx = parseInt(card.dataset.index, 10);
                openLightbox(idx);
            });
        });
    }

    function openLightbox(index) {
        if (index < 0 || index >= allPhotos.length) return;
        currentIndex = index;
        var photo = allPhotos[index];
        var url = '/api/gallery/' + photo.id;

        // Remove existing
        if (lightboxOverlay) lightboxOverlay.remove();

        var overlay = document.createElement('div');
        overlay.className = 'lightbox-overlay';
        overlay.innerHTML =
            '<button class="lightbox-nav prev" aria-label="Previous">&#8249;</button>' +
            '<img src="' + url + '" alt="Photo">' +
            '<button class="lightbox-nav next" aria-label="Next">&#8250;</button>' +
            '<div class="lightbox-actions">' +
                '<a class="lightbox-btn download" href="' + url + '" download>Download</a>' +
                '<button class="lightbox-btn close">Close</button>' +
            '</div>';

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeLightbox();
        });
        overlay.querySelector('.lightbox-btn.close').addEventListener('click', closeLightbox);
        overlay.querySelector('.lightbox-nav.prev').addEventListener('click', function () {
            navigateLightbox(-1);
        });
        overlay.querySelector('.lightbox-nav.next').addEventListener('click', function () {
            navigateLightbox(1);
        });

        document.body.appendChild(overlay);
        lightboxOverlay = overlay;
        requestAnimationFrame(function () { overlay.classList.add('active'); });
    }

    function navigateLightbox(direction) {
        var newIndex = currentIndex + direction;
        if (newIndex < 0 || newIndex >= allPhotos.length) return;
        openLightbox(newIndex);
    }

    function closeLightbox() {
        if (lightboxOverlay) {
            lightboxOverlay.remove();
            lightboxOverlay = null;
            currentIndex = -1;
        }
    }

    document.addEventListener('DOMContentLoaded', init);
})();
