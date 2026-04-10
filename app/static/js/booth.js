/**
 * booth.js — Photobooth kiosk WebSocket client
 *
 * Manages the full booth lifecycle: idle attract screen, mode selection,
 * camera preview with countdown, capture flash, processing progress,
 * review with effects, print with QR, and thank-you.
 */

/* CSS filter mapping for live preview (client-side only) */
const CSS_FILTERS = {
    none: 'none',
    bw: 'grayscale(100%)',
    sepia: 'sepia(80%)',
    vintage: 'sepia(40%) contrast(90%) saturate(80%)',
    warm: 'sepia(20%) saturate(120%)',
    cool: 'hue-rotate(20deg) saturate(90%)',
    blur: 'blur(2px)',
    high_contrast: 'contrast(150%)',
    // sharpen can't be done with CSS filters, skip for preview
    cartoon: 'contrast(150%) saturate(120%)',
    pencil_sketch: 'grayscale(100%) contrast(200%) brightness(120%)',
    watercolor: 'saturate(130%) blur(0.5px)',
    pop_art: 'contrast(200%) saturate(200%)',
    oil_painting: 'saturate(110%) contrast(110%)',
};

class SoundManager {
    constructor(config) {
        this.enabled = config.enabled !== false;
        this.volume = config.volume || 0.8;
        this.sounds = {};
        this.preload(config);
    }

    preload(config) {
        const soundFiles = {
            countdown_beep: config.countdown_beep || 'sounds/beep.mp3',
            shutter: config.shutter || 'sounds/shutter.mp3',
            applause: config.applause || 'sounds/applause.mp3',
            click: config.click || 'sounds/click.mp3',
            error: config.error || 'sounds/error.mp3',
        };
        for (const [name, src] of Object.entries(soundFiles)) {
            const audio = new Audio('/static/' + src);
            audio.volume = this.volume;
            audio.preload = 'auto';
            this.sounds[name] = audio;
        }
    }

    play(name) {
        if (!this.enabled) return;
        const sound = this.sounds[name];
        if (sound) {
            sound.currentTime = 0;
            sound.play().catch(function () {}); // Ignore autoplay restrictions
        }
    }

    setVolume(vol) {
        this.volume = Math.max(0, Math.min(1, vol));
        for (const sound of Object.values(this.sounds)) {
            sound.volume = this.volume;
        }
    }

    setEnabled(enabled) {
        this.enabled = enabled;
    }
}

class BoothApp {
    constructor() {
        this.ws = null;
        this.state = 'idle';
        this.sections = document.querySelectorAll('section[data-state]');
        this.reconnectDelay = 1000;
        this.countdownTimer = null;
        this.selectedFilter = 'none';
        this.i18n = new I18n('en');
        this.sounds = null; // Initialized when server sends sound_config
    }

    init() {
        this.connect();
        this.bindEvents();
        this.setupSettingsAccess();
        this.loadConfig();
        this.loadBranding();
    }

    /* ------------------------------------------------------------------ */
    /*  Config loading (for idle timeout, etc.)                             */
    /* ------------------------------------------------------------------ */

    async loadConfig() {
        try {
            var res = await fetch('/api/admin/config');
            this.config = await res.json();
        } catch (e) {
            console.warn('[booth] failed to load config:', e);
            this.config = null;
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Branding / logo                                                    */
    /* ------------------------------------------------------------------ */

    async loadBranding() {
        try {
            var res = await fetch('/api/admin/branding');
            var data = await res.json();
            var logoImg = document.getElementById('logo-img');
            if (data.logo_url && logoImg) {
                logoImg.src = data.logo_url;
                logoImg.style.display = 'block';
            }
        } catch (e) {
            // Branding endpoint may not be available
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Idle timeout                                                        */
    /* ------------------------------------------------------------------ */

    resetIdleTimer() {
        clearTimeout(this.idleTimer);
        if (['choose', 'review'].includes(this.state)) {
            var timeout = (this.config && this.config.display && this.config.display.idle_timeout) || 60;
            var self = this;
            this.idleTimer = setTimeout(function () {
                self.send('cancel');
            }, timeout * 1000);
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Secret settings access (5-tap top-right corner)                    */
    /* ------------------------------------------------------------------ */

    setupSettingsAccess() {
        var tapCount = 0;
        var tapTimer = null;
        var corner = document.createElement('div');
        corner.style.cssText = 'position:fixed;top:0;right:0;width:80px;height:80px;z-index:9999;';
        document.body.appendChild(corner);

        corner.addEventListener('click', function () {
            tapCount++;
            clearTimeout(tapTimer);
            tapTimer = setTimeout(function () { tapCount = 0; }, 2000);
            if (tapCount >= 5) {
                tapCount = 0;
                window.open('/admin', '_blank');
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  WebSocket                                                         */
    /* ------------------------------------------------------------------ */

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/ws/booth`);

        this.ws.onopen = () => {
            console.log('[booth] connected');
            this.reconnectDelay = 1000;
            document.body.classList.remove('offline');
        };

        this.ws.onmessage = (e) => this.handleMessage(JSON.parse(e.data));

        this.ws.onclose = () => {
            console.log('[booth] disconnected, reconnecting...');
            document.body.classList.add('offline');
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000);
        };

        this.ws.onerror = () => {
            // onclose will handle reconnection
        };
    }

    send(action, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(Object.assign({ action: action }, data || {})));
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Message handling                                                   */
    /* ------------------------------------------------------------------ */

    handleMessage(msg) {
        switch (msg.type) {
            case 'state_change':
                // Initialize sound manager from server config on first state_change
                if (msg.sound_config && !this.sounds) {
                    this.sounds = new SoundManager(msg.sound_config);
                    console.log('[booth] sound manager initialized');
                }
                this.showState(msg.state);
                break;
            case 'countdown':
                this.updateCountdown(msg.seconds);
                break;
            case 'capture_complete':
                this.onCaptureComplete(msg);
                break;
            case 'processing_progress':
                this.updateProgress(msg.percent);
                break;
            case 'result_ready':
                this.showResult(msg);
                break;
            case 'print_status':
                this.updatePrintStatus(msg.status);
                break;
            case 'pose_prompt':
                this.showPosePrompt(msg.text, msg.capture, msg.total);
                break;
            case 'auto_transition':
                this.handleAutoTransition(msg.target);
                break;
            case 'error':
                console.error('[booth] error:', msg.message);
                if (this.sounds) this.sounds.play('error');
                this.showError(msg.message);
                break;
        }
    }

    /* ------------------------------------------------------------------ */
    /*  State transitions                                                  */
    /* ------------------------------------------------------------------ */

    showState(state) {
        var previousState = this.state;
        this.state = state;
        this.sections.forEach(function (s) {
            var isActive = s.dataset.state === state;
            s.classList.toggle('active', isActive);
        });

        // Play sounds on state transitions
        if (this.sounds && state === 'capture' && previousState !== 'capture') {
            this.sounds.play('shutter');
        }

        // Reset idle timer on every state change
        this.resetIdleTimer();

        // Reset safety timer on every state change
        this.resetSafetyTimer();

        // Reset choose screen when entering it
        if (state === 'choose') {
            this.resetChooseScreen();
        }

        // State-specific setup / teardown
        if (state === 'preview') {
            this.startPreview();
            this.startCountdown();
        } else if (state !== 'preview' && previousState === 'preview') {
            this.stopCountdown();
        }
        if (state === 'idle') {
            this.stopPreview();
            this.hidePosePrompt();
        } else {
            this.hidePosePrompt();
        }

        // Print screen auto-advance
        if (state === 'print') {
            this.startPrintTimer();
        }
        if (previousState === 'print') {
            this.stopPrintTimer();
        }
    }

    startPreview() {
        var img = document.getElementById('camera-preview');
        var noCamera = document.getElementById('no-camera');
        if (noCamera) noCamera.style.display = 'none';
        if (img) {
            img.style.display = '';
            // Detect stream failure (no camera, broken connection, etc.)
            img.onerror = function () {
                console.warn('[booth] camera stream failed');
                img.style.display = 'none';
                if (noCamera) noCamera.style.display = '';
            };
            // Cache-bust the MJPEG stream URL to force a fresh connection
            img.src = '/api/camera/stream?' + Date.now();
        }
        // Apply CSS mirror for zero-latency selfie mode
        this.applyPreviewMirror();
    }

    async applyPreviewMirror() {
        try {
            var res = await fetch('/api/admin/camera/framing');
            var framing = await res.json();
            var img = document.getElementById('camera-preview');
            if (img) {
                img.classList.toggle('mirrored', !!framing.mirror_preview);
            }
        } catch (e) {
            // Framing endpoint may not be available
        }
    }

    stopPreview() {
        var img = document.getElementById('camera-preview');
        var noCamera = document.getElementById('no-camera');
        if (img) {
            img.onerror = null;
            img.src = '';
        }
        if (noCamera) noCamera.style.display = 'none';
    }

    /* ------------------------------------------------------------------ */
    /*  Countdown                                                          */
    /* ------------------------------------------------------------------ */

    updateCountdown(seconds) {
        var el = document.getElementById('countdown');
        if (!el) return;

        if (seconds > 0) {
            el.textContent = seconds;
            el.classList.add('tick');
            setTimeout(function () { el.classList.remove('tick'); }, 300);
            // Play countdown beep on each tick
            if (this.sounds) this.sounds.play('countdown_beep');
        } else {
            el.textContent = '';
        }
    }

    startCountdown() {
        this.stopCountdown();
        var countdownSeconds = 5;
        var remaining = countdownSeconds;
        var self = this;
        this.updateCountdown(remaining);
        this.countdownTimer = setInterval(function () {
            remaining--;
            if (remaining > 0) {
                self.updateCountdown(remaining);
            } else {
                self.stopCountdown();
                self.updateCountdown(0);
                // Trigger capture
                if (self.sounds) self.sounds.play('shutter');
                self.send('capture');
            }
        }, 1000);
    }

    stopCountdown() {
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }
        var el = document.getElementById('countdown');
        if (el) el.textContent = '';
    }

    /* ------------------------------------------------------------------ */
    /*  Capture progress dots                                              */
    /* ------------------------------------------------------------------ */

    onCaptureComplete(msg) {
        var dots = document.getElementById('capture-dots');
        if (dots) {
            dots.innerHTML = '';
            for (var i = 0; i < msg.total; i++) {
                var dot = document.createElement('span');
                dot.className = 'dot' + (i < msg.index ? ' filled' : '');
                dots.appendChild(dot);
            }
        }
        // Auto-advance after a brief pause
        var self = this;
        setTimeout(function () {
            self.send('capture_advance');
        }, 500);
    }

    /* ------------------------------------------------------------------ */
    /*  Processing progress                                                */
    /* ------------------------------------------------------------------ */

    updateProgress(percent) {
        var fill = document.getElementById('progress');
        if (fill) {
            fill.style.width = percent + '%';
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Result display                                                     */
    /* ------------------------------------------------------------------ */

    showResult(msg) {
        var reviewImg = document.getElementById('review-photo');
        if (reviewImg) reviewImg.src = msg.url;

        var printImg = document.getElementById('print-photo');
        if (printImg) printImg.src = msg.url;

        if (msg.qr_url) {
            var qr = document.getElementById('qr-code');
            if (qr) qr.src = msg.qr_url;
        }

        // Play applause when the result is ready
        if (this.sounds) this.sounds.play('applause');

        // Advance to review state
        var self = this;
        setTimeout(function () {
            self.send('result_ready');
        }, 500);
    }

    /* ------------------------------------------------------------------ */
    /*  Print status                                                       */
    /* ------------------------------------------------------------------ */

    updatePrintStatus(status) {
        var el = document.getElementById('print-status');
        if (!el) return;

        var spinner = document.getElementById('print-spinner');
        var statusArea = document.getElementById('print-status-area');

        var messages = {
            printing:      this.i18n.t('printing'),
            done:          this.i18n.t('print_complete'),
            error:         this.i18n.t('print_error'),
            no_printer:    this.i18n.t('no_printer'),
            limit_reached: 'Print limit reached -- scan QR to download!'
        };
        el.textContent = messages[status] || status;
        el.className = 'print-status-text ' + status;

        // Hide spinner when print is done or errored
        if (spinner) {
            spinner.style.display = (status === 'printing') ? '' : 'none';
        }

        // Hide entire status area if no printer (QR is the star)
        if (statusArea && (status === 'no_printer')) {
            statusArea.style.display = 'none';
        }

        // Play error sound on print errors
        if (status === 'error' && this.sounds) {
            this.sounds.play('error');
        }
    }

    handleAutoTransition(target) {
        if (target === 'thankyou') {
            this.send('done');
        } else if (target === 'idle') {
            this.send('auto_idle');
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Print screen auto-advance timer                                    */
    /* ------------------------------------------------------------------ */

    startPrintTimer() {
        var self = this;
        this.printTimer = setTimeout(function () {
            self.send('done');
        }, 15000); // 15 seconds then auto-advance
    }

    stopPrintTimer() {
        if (this.printTimer) {
            clearTimeout(this.printTimer);
            this.printTimer = null;
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Review filter preview                                              */
    /* ------------------------------------------------------------------ */

    applyReviewFilter(filterName) {
        this.selectedFilter = filterName;
        var img = document.getElementById('review-photo');
        if (img) {
            img.style.filter = CSS_FILTERS[filterName] || 'none';
        }

        // Update active button in review filters
        var buttons = document.querySelectorAll('#review-filters .filter-btn');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].classList.toggle('active', buttons[i].dataset.filter === filterName);
        }

        // Notify server of the selected effect
        this.send('select_effect', { effect: filterName });
    }

    /* ------------------------------------------------------------------ */
    /*  Live filter preview                                                */
    /* ------------------------------------------------------------------ */

    selectFilter(filterName) {
        this.selectedFilter = filterName;
        var img = document.getElementById('camera-preview');
        if (img) {
            img.style.filter = CSS_FILTERS[filterName] || 'none';
        }

        // Update active button
        var buttons = document.querySelectorAll('.filter-btn');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].classList.toggle('active', buttons[i].dataset.filter === filterName);
        }

        // Notify server of the selected effect
        this.send('select_effect', { effect: filterName });
    }

    /* ------------------------------------------------------------------ */
    /*  Pose prompts                                                       */
    /* ------------------------------------------------------------------ */

    showPosePrompt(text, capture, total) {
        var el = document.getElementById('pose-prompt');
        if (el) {
            el.textContent = text;
            el.classList.add('visible');
            setTimeout(function () { el.classList.remove('visible'); }, 3000);
        }
    }

    hidePosePrompt() {
        var el = document.getElementById('pose-prompt');
        if (el) {
            el.textContent = '';
            el.classList.remove('visible');
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Photo counter                                                      */
    /* ------------------------------------------------------------------ */

    updatePhotoCounter(counters) {
        var el = document.getElementById('photo-counter');
        if (el && counters && counters.total_taken > 0) {
            el.textContent = 'Photos taken: ' + counters.total_taken;
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Slideshow attract mode                                             */
    /* ------------------------------------------------------------------ */

    startSlideshow() {
        this.loadSlidePhotos();
        this.slideshowTimer = setInterval(() => this.nextSlide(), 4000);
        this.loadPhotoCounter();
    }

    async loadSlidePhotos() {
        try {
            var res = await fetch('/api/gallery/?limit=20');
            var data = await res.json();
            this.slidePhotos = data.photos || [];
            this.slideIndex = 0;
            if (this.slidePhotos.length > 0) this.showSlide();
        } catch (e) {
            console.warn('[booth] slideshow fetch failed:', e);
        }
    }

    nextSlide() {
        if (!this.slidePhotos || this.slidePhotos.length === 0) return;
        this.slideIndex = (this.slideIndex + 1) % this.slidePhotos.length;
        this.showSlide();
    }

    showSlide() {
        var photo = this.slidePhotos[this.slideIndex];
        var slideEl = document.getElementById('slideshow');
        if (slideEl && photo) {
            slideEl.style.backgroundImage = 'url(/api/gallery/' + photo.id + ')';
            slideEl.classList.add('visible');
        }
    }

    stopSlideshow() {
        if (this.slideshowTimer) {
            clearInterval(this.slideshowTimer);
            this.slideshowTimer = null;
        }
        var slideEl = document.getElementById('slideshow');
        if (slideEl) slideEl.classList.remove('visible');
    }

    async loadPhotoCounter() {
        try {
            var res = await fetch('/api/admin/counters');
            var data = await res.json();
            var el = document.getElementById('photo-counter');
            if (el && data.total_taken > 0) {
                el.textContent = 'Photos taken: ' + data.total_taken;
            }
        } catch (e) {
            // Counter endpoint may not be available yet
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Template picker                                                    */
    /* ------------------------------------------------------------------ */

    async showTemplatePicker(mode, count) {
        this._pendingMode = mode;
        this._pendingCount = count;

        var res = await fetch('/api/admin/templates');
        var data = await res.json();
        var grid = document.getElementById('template-picker-grid');
        grid.innerHTML = '';
        var self = this;

        for (var i = 0; i < data.templates.length; i++) {
            await (async function (name) {
                var tplRes = await fetch('/api/admin/templates/' + name);
                var tpl = await tplRes.json();

                var card = document.createElement('button');
                card.className = 'template-card';
                card.dataset.template = name;

                // Create mini canvas preview
                var preview = document.createElement('div');
                preview.className = 'template-mini-preview';
                preview.style.aspectRatio = tpl.width_inches + ' / ' + tpl.height_inches;
                preview.style.background = tpl.background || '#fff';

                for (var s = 0; s < tpl.slots.length; s++) {
                    var slot = tpl.slots[s];
                    var slotEl = document.createElement('div');
                    slotEl.className = 'mini-slot';
                    slotEl.style.left = (slot.x * 100) + '%';
                    slotEl.style.top = (slot.y * 100) + '%';
                    slotEl.style.width = (slot.width * 100) + '%';
                    slotEl.style.height = (slot.height * 100) + '%';
                    if (slot.rotation) slotEl.style.transform = 'rotate(' + slot.rotation + 'deg)';
                    preview.appendChild(slotEl);
                }

                card.appendChild(preview);
                var label = document.createElement('span');
                label.className = 'template-card-name';
                label.textContent = name.replace(/-/g, ' ');
                card.appendChild(label);

                card.addEventListener('click', function () {
                    if (self.sounds) self.sounds.play('click');
                    self.send('select_template', { template: name });
                    self.send('choose', {
                        mode: self._pendingMode,
                        count: self._pendingCount,
                        template: name
                    });
                    // Hide picker, show mode chooser again for next time
                    document.getElementById('template-picker').style.display = 'none';
                    document.querySelector('.choose-grid').style.display = '';
                });

                grid.appendChild(card);
            })(data.templates[i]);
        }

        // Show picker, hide mode chooser
        document.querySelector('.choose-grid').style.display = 'none';
        document.querySelector('[data-state="choose"] .section-heading').style.display = 'none';
        document.getElementById('template-picker').style.display = '';
    }

    resetChooseScreen() {
        // Reset template picker visibility when re-entering choose
        var picker = document.getElementById('template-picker');
        var grid = document.querySelector('.choose-grid');
        var heading = document.querySelector('[data-state="choose"] .section-heading');
        if (picker) picker.style.display = 'none';
        if (grid) grid.style.display = '';
        if (heading) heading.style.display = '';
    }

    /* ------------------------------------------------------------------ */
    /*  Safety timeout — prevent booth from freezing in any state          */
    /* ------------------------------------------------------------------ */

    resetSafetyTimer() {
        clearTimeout(this.safetyTimer);
        // If stuck in any non-idle state for 60s, force back to idle
        if (this.state !== 'idle') {
            var self = this;
            this.safetyTimer = setTimeout(function () {
                console.warn('[booth] Safety timeout — returning to idle');
                self.send('cancel');
                // Force UI back even if server doesn't respond
                setTimeout(function () {
                    if (self.state !== 'idle') {
                        self.showState('idle');
                    }
                }, 3000);
            }, 60000);
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Error toast                                                        */
    /* ------------------------------------------------------------------ */

    showError(message) {
        var toast = document.getElementById('error-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'error-toast';
            toast.className = 'error-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('visible');
        setTimeout(function () { toast.classList.remove('visible'); }, 4000);
    }

    /* ------------------------------------------------------------------ */
    /*  Event binding                                                      */
    /* ------------------------------------------------------------------ */

    bindEvents() {
        var self = this;

        // Reset idle timer on any user interaction
        document.addEventListener('click', function () { self.resetIdleTimer(); });
        document.addEventListener('touchstart', function () { self.resetIdleTimer(); });

        // Idle: tap anywhere to start
        var idle = document.querySelector('[data-state="idle"]');
        if (idle) {
            idle.addEventListener('click', function () {
                if (self.sounds) self.sounds.play('click');
                self.send('start');
            });
        }

        // Choose: pick an option
        var options = document.querySelectorAll('.choose-option');
        for (var i = 0; i < options.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    if (self.sounds) self.sounds.play('click');
                    var mode = btn.dataset.mode;
                    var count = parseInt(btn.dataset.count, 10);

                    // Check if guest picks template
                    var guestPicks = self.config && self.config.picture && self.config.picture.guest_picks_template;
                    if (guestPicks) {
                        self.showTemplatePicker(mode, count);
                    } else {
                        self.send('choose', { mode: mode, count: count });
                    }
                });
            })(options[i]);
        }

        // Cancel buttons
        var cancels = document.querySelectorAll('[data-action="cancel"]');
        for (var j = 0; j < cancels.length; j++) {
            cancels[j].addEventListener('click', function () {
                if (self.sounds) self.sounds.play('click');
                self.send('cancel');
            });
        }

        // Review action buttons (retake, print, done)
        var actions = document.querySelectorAll('[data-action]');
        for (var k = 0; k < actions.length; k++) {
            (function (btn) {
                var action = btn.dataset.action;
                if (action === 'retake' || action === 'print' || action === 'done') {
                    btn.addEventListener('click', function () {
                        if (self.sounds) self.sounds.play('click');
                        self.send(action);
                    });
                }
            })(actions[k]);
        }

        // Preview filter buttons
        var previewFilterBtns = document.querySelectorAll('.preview-filters .filter-btn');
        for (var n = 0; n < previewFilterBtns.length; n++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    self.selectFilter(btn.dataset.filter);
                });
            })(previewFilterBtns[n]);
        }

        // Review filter buttons
        var reviewFilterBtns = document.querySelectorAll('#review-filters .filter-btn');
        for (var n2 = 0; n2 < reviewFilterBtns.length; n2++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    if (self.sounds) self.sounds.play('click');
                    self.applyReviewFilter(btn.dataset.filter);
                });
            })(reviewFilterBtns[n2]);
        }

        // Ripple effect on buttons
        var buttons = document.querySelectorAll('.btn-primary, .btn-secondary, .btn-text, .choose-option');
        for (var m = 0; m < buttons.length; m++) {
            buttons[m].addEventListener('click', function (e) {
                var rect = this.getBoundingClientRect();
                var ripple = document.createElement('span');
                ripple.className = 'ripple';
                ripple.style.left = (e.clientX - rect.left) + 'px';
                ripple.style.top = (e.clientY - rect.top) + 'px';
                this.appendChild(ripple);
                setTimeout(function () { ripple.remove(); }, 600);
            });
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function () {
    var app = new BoothApp();
    app.init();
});
