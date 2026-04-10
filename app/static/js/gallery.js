/**
 * gallery.js — Event gallery page
 *
 * Fetches photos from the API and renders a responsive grid.
 * Auto-refreshes every 30 seconds. Tap to view/download.
 */

(function () {
    var REFRESH_INTERVAL = 30000;
    var currentPhotoId = null;

    function init() {
        loadGallery();
        setInterval(loadGallery, REFRESH_INTERVAL);

        document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
        document.getElementById('lightbox').addEventListener('click', function (e) {
            if (e.target === this) closeLightbox();
        });

        // Load event name from config
        loadEventName();
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
            renderGrid(data.photos || []);
        } catch (e) {
            console.error('[gallery] fetch failed:', e);
        }
    }

    function renderGrid(photos) {
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

        // Build new HTML
        var html = '';
        for (var i = 0; i < photos.length; i++) {
            var photo = photos[i];
            html += '<div class="gallery-item" data-id="' + photo.id + '">';
            html += '<img src="/api/gallery/' + photo.id + '/thumbnail" alt="Photo" loading="lazy">';
            html += '</div>';
        }
        grid.innerHTML = html;

        // Bind click events
        var items = grid.querySelectorAll('.gallery-item');
        for (var j = 0; j < items.length; j++) {
            (function (item) {
                item.addEventListener('click', function () {
                    openLightbox(item.dataset.id);
                });
            })(items[j]);
        }
    }

    function openLightbox(photoId) {
        currentPhotoId = photoId;
        var lightbox = document.getElementById('lightbox');
        var img = document.getElementById('lightbox-img');
        var download = document.getElementById('lightbox-download');

        img.src = '/api/gallery/' + photoId;
        download.href = '/api/gallery/' + photoId;
        lightbox.classList.add('active');
    }

    function closeLightbox() {
        var lightbox = document.getElementById('lightbox');
        lightbox.classList.remove('active');
        currentPhotoId = null;
    }

    // Escape key to close lightbox
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeLightbox();
    });

    document.addEventListener('DOMContentLoaded', init);
})();
