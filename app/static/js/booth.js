/**
 * booth.js — Photobooth kiosk WebSocket client
 *
 * Manages the full booth lifecycle: idle attract screen, mode selection,
 * camera preview with countdown, capture flash, processing progress,
 * review with effects, print with QR, and thank-you.
 */

class SoundManager {
    constructor(config) {
        this.enabled = config.enabled !== false;
        this.volume = config.volume || 0.8;
        this.sounds = {};
        this.preload(config);
    }

    preload(config) {
        const soundFiles = {
            countdown_beep: config.countdown_beep || 'sounds/beep.wav',
            shutter: config.shutter || 'sounds/shutter.wav',
            applause: config.applause || 'sounds/applause.wav',
            click: config.click || 'sounds/click.wav',
            error: config.error || 'sounds/error.wav',
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
        this.selectedEffect = 'none';
        this.selectedBackground = null;
        this.pendingMode = null;
        this.pendingTemplate = null;
        this.i18n = new I18n('en');
        this.sounds = null; // Initialized when server sends sound_config
    }

    init() {
        this.connect();
        this.bindEvents();
        this.setupSettingsAccess();
        this.loadConfig();
        this.loadBranding();
        this.startSlideshow();
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

    applyConfigUI() {
        // Hide print button if no printer
        var printBtn = document.querySelector('[data-action="print"]');
        if (printBtn && this.wsConfig && !this.wsConfig.has_printer) {
            printBtn.style.display = 'none';
        }
    }

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
        // Safety timer handles timeouts now (90s warning, 120s reset)
        clearTimeout(this.idleTimer);
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
                }
                if (msg.config) {
                    this.wsConfig = msg.config;
                    this.applyConfigUI();
                }
                // Track the real server state (for logic checks)
                this._serverState = msg.state;

                // Show processing screen during capture (no separate capture screen)
                var displayState = msg.state;
                if (msg.state === 'capture') {
                    // Always show processing screen during capture
                    displayState = 'processing';
                    var pt = document.getElementById('processing-text');
                    if (pt) pt.textContent = this._isGifMode ? 'Recording...' : 'Capturing...';
                    var ps = document.getElementById('processing-step');
                    if (ps) ps.textContent = '';
                    var pf = document.getElementById('progress');
                    if (pf) pf.style.width = '0%';
                    // Show recording overlay on top for GIF
                    if (this._isGifMode) {
                        this.showRecordingOverlay();
                    }
                }
                this.showState(displayState);
                break;
            case 'countdown':
                this.updateCountdown(msg.seconds);
                break;
            case 'capture_progress':
                this.onCaptureProgress(msg);
                break;
            case 'capture_complete':
                this.onCaptureComplete(msg);
                break;
            case 'processing_progress':
                // Once processing starts, hide the recording overlay
                if (msg.step === 'compositing' || msg.step === 'applying_effect') {
                    this.hideRecordingOverlay();
                }
                this.updateProgress(msg.percent, msg.step, msg.frame, msg.total_frames);
                if (this.state === 'capture') {
                    this.send('capture_advance');
                }
                break;
            case 'result_ready':
                this.showResult(msg);
                break;
            case 'cloud_upload_complete':
                // Update QR to point to the specific photo, not just the album
                if (msg.photo_url) {
                    var qr = document.getElementById('qr-code');
                    if (qr) qr.src = '/api/share/qr?url=' + encodeURIComponent(msg.photo_url);
                    var reviewQr = document.getElementById('review-qr-img');
                    if (reviewQr) reviewQr.src = '/api/share/qr?url=' + encodeURIComponent(msg.photo_url);
                }
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
            case 'button':
                this.handleHardwareButton(msg.action);
                break;
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Hardware button handler (red=cycle, green=select)                   */
    /* ------------------------------------------------------------------ */

    handleHardwareButton(action) {
        // Show button hints when hardware buttons are used
        var hints = document.getElementById('button-hints');
        if (hints) hints.style.display = 'flex';

        // Find all visible option cards/buttons on the current screen
        var items = [];
        var activeSection = document.querySelector('section[data-state].active');
        if (!activeSection) return;

        // Check what's visible — use offsetParent to detect hidden elements
        function isVisible(el) { return el && el.offsetParent !== null; }

        var effectPicker = document.getElementById('effect-picker');
        var templatePicker = document.getElementById('template-picker');
        var bgPicker = document.getElementById('bg-picker');

        if (isVisible(effectPicker)) {
            items = Array.from(effectPicker.querySelectorAll('.effect-card'));
        } else if (isVisible(bgPicker)) {
            items = Array.from(bgPicker.querySelectorAll('.bg-card'));
        } else if (isVisible(templatePicker)) {
            items = Array.from(templatePicker.querySelectorAll('.template-card'));
        } else {
            // Fall back to choose grid options
            items = Array.from(document.querySelectorAll('.choose-option'));
        }

        console.log('[booth] button action=' + action + ', items found=' + items.length);
        if (items.length === 0) return;

        // Find current highlighted item
        var currentIdx = items.findIndex(function(el) { return el.classList.contains('btn-highlighted'); });

        if (action === 'cycle') {
            // Red button: move highlight to next item
            if (currentIdx >= 0) items[currentIdx].classList.remove('btn-highlighted');
            var nextIdx = (currentIdx + 1) % items.length;
            items[nextIdx].classList.add('btn-highlighted');
            items[nextIdx].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            if (this.sounds) this.sounds.play('click');
        } else if (action === 'select') {
            // Green button: click the highlighted item (or first if none highlighted)
            var target = currentIdx >= 0 ? items[currentIdx] : items[0];
            if (this.sounds) this.sounds.play('click');
            target.click();
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

        // Hide recording overlay only when going to review/idle (not processing)
        if (state === 'review' || state === 'idle' || state === 'choose') {
            this.hideRecordingOverlay();
        }

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
            // Multi-shot: pause between captures
            console.log('[booth] preview: captureCount=' + this.captureCount + ' captureIndex=' + this.captureIndex);
            if (this.captureCount > 1 && this.captureIndex > 0 && this.captureIndex < this.captureCount) {
                // Show "Shot X of Y" then effect picker
                var self = this;
                var countdownEl = document.getElementById('countdown');
                var shotNum = (this.captureIndex || 0) + 1;
                var totalShots = this.captureCount || 4;
                if (countdownEl) {
                    countdownEl.textContent = 'Shot ' + shotNum + ' of ' + totalShots + '!';
                    countdownEl.style.fontSize = 'clamp(2rem, 5vw, 3rem)';
                }
                // After 1.5s show effect picker, auto-start countdown after 5s total
                setTimeout(function () {
                    if (countdownEl) {
                        countdownEl.textContent = '';
                        countdownEl.style.fontSize = '';
                    }
                    self.showPerShotEffectPicker();
                }, 1500);
            } else {
                this.startCountdown();
            }
        }
        // Show selected effect label on preview
        if (state === 'preview') {
            var effectLabel = document.getElementById('preview-effect-label');
            if (effectLabel) {
                var effectNames = {
                    none: '', bw: 'B&W', sepia: 'Sepia', vintage: 'Vintage',
                    cartoon: 'Cartoon', pencil_sketch: 'Sketch', watercolor: 'Watercolor',
                    pop_art: 'Pop Art', oil_painting: 'Oil Paint', warm: 'Warm', cool: 'Cool'
                };
                var label = effectNames[this.selectedEffect] || '';
                effectLabel.textContent = label;
                effectLabel.style.display = label ? '' : 'none';
            }
        } else if (state !== 'preview' && previousState === 'preview') {
            this.stopCountdown();
        }
        if (state === 'idle') {
            this.stopPreview();
            this.hidePosePrompt();
            this._multiShotActive = false;
            this.startSlideshow();
        } else {
            this.hidePosePrompt();
            if (previousState === 'idle') {
                this.stopSlideshow();
            }
        }

        // Processing timeout — if stuck, force advance
        if (state === 'processing') {
            var self = this;
            this._processingTimeout = setTimeout(function () {
                console.warn('Processing timeout — forcing advance');
                self.send('result_ready');
                setTimeout(function () {
                    if (self.state === 'processing') {
                        self.showState('idle');
                    }
                }, 3000);
            }, 120000); // 2 minutes
        }
        if (previousState === 'processing' && this._processingTimeout) {
            clearTimeout(this._processingTimeout);
        }

        // Print screen auto-advance
        if (state === 'print') {
            this.startPrintTimer();
        }
        if (previousState === 'print') {
            this.stopPrintTimer();
        }

        // Update physical button hint labels
        this.updateButtonHints(state);
    }

    updateButtonHints(state) {
        var green = document.getElementById('hint-green');
        var red = document.getElementById('hint-red');
        if (!green || !red) return;

        var hints = {
            idle:       { green: 'Press to start!', red: 'Press to start!' },
            choose:     { green: 'Select', red: 'Next' },
            preview:    { green: 'Cancel', red: 'Cancel' },
            capture:    { green: '', red: '' },
            processing: { green: '', red: '' },
            review:     { green: 'Done', red: 'Retake' },
            print:      { green: 'Done', red: 'Done' },
            thankyou:   { green: 'Next', red: 'Next' },
        };

        var h = hints[state] || { green: '', red: '' };
        green.textContent = h.green;
        red.textContent = h.red;

        // Hide hints when no actions are available
        var container = document.getElementById('button-hints');
        if (container) {
            container.style.display = (h.green || h.red) ? 'flex' : 'none';
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
        var countdownSeconds = 3;
        var remaining = countdownSeconds;
        var self = this;
        this.updateCountdown(remaining);
        this.countdownTimer = setInterval(function () {
            remaining--;
            if (remaining > 0) {
                self.updateCountdown(remaining);
            } else {
                self.stopCountdown();
                var countdownEl = document.getElementById('countdown');
                if (countdownEl) countdownEl.textContent = '';
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
    /*  Recording overlay (GIF/boomerang burst capture)                     */
    /* ------------------------------------------------------------------ */

    showRecordingOverlay() {
        var overlay = document.getElementById('recording-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            // Build dots for progress
            var dots = document.getElementById('recording-dots');
            if (dots) {
                dots.innerHTML = '';
                for (var i = 0; i < 8; i++) {
                    var dot = document.createElement('span');
                    dot.className = 'dot';
                    dots.appendChild(dot);
                }
            }
            // Reset counter
            var counter = document.getElementById('recording-counter');
            if (counter) {
                counter.textContent = '1';
                counter.classList.remove('pop');
            }
        }
    }

    hideRecordingOverlay() {
        var overlay = document.getElementById('recording-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    /* ------------------------------------------------------------------ */
    /*  Capture progress dots                                              */
    /* ------------------------------------------------------------------ */

    onCaptureProgress(msg) {
        // Always update processing screen
        var processingText = document.getElementById('processing-text');
        var processingStep = document.getElementById('processing-step');
        var processingIcon = document.querySelector('.processing-icon');
        var fill = document.getElementById('progress');

        if (processingText) processingText.textContent = 'Recording...';
        if (processingStep) processingStep.textContent = msg.frame + ' of ' + msg.total;
        if (processingIcon) {
            processingIcon.textContent = msg.frame;
            processingIcon.style.fontSize = '6rem';
            processingIcon.classList.remove('pop');
            void processingIcon.offsetWidth;
            processingIcon.classList.add('pop');
        }
        if (fill && msg.total) fill.style.width = (msg.frame / msg.total * 40) + '%';

        // Also update recording overlay if visible
        if (this._isGifMode) {
            var counter = document.getElementById('recording-counter');
            var dots = document.getElementById('recording-dots');

            if (counter) {
                counter.textContent = msg.frame;
                counter.classList.remove('pop');
                void counter.offsetWidth;
                counter.classList.add('pop');
            }

            if (dots) {
                var dotEls = dots.querySelectorAll('.dot');
                for (var i = 0; i < dotEls.length; i++) {
                    if (i < msg.frame) dotEls[i].classList.add('filled');
                }
            }
        } else {
            // Single/multi photo: show progress on processing screen
            var processingText = document.getElementById('processing-text');
            var processingStep = document.getElementById('processing-step');
            var fill = document.getElementById('progress');
            var icon = document.querySelector('.processing-icon');

            if (icon) icon.textContent = msg.frame;
            if (icon) icon.style.fontSize = '6rem';
            if (processingText) processingText.textContent = 'Strike a pose!';
            if (processingStep) processingStep.textContent = msg.frame + ' of ' + msg.total;
            if (fill && msg.total) fill.style.width = (msg.frame / msg.total * 50) + '%';

            // Flash effect on each frame
            if (icon) {
                icon.classList.remove('tick');
                void icon.offsetWidth;
                icon.classList.add('tick');
            }
        }
    }

    onCaptureComplete(msg) {
        this.captureCount = msg.total || 1;
        this.captureIndex = msg.index || 0;
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

    updateProgress(percent, step, frame, totalFrames) {
        var fill = document.getElementById('progress');
        if (fill) fill.style.width = percent + '%';

        var stepEl = document.getElementById('processing-step');
        var textEl = document.getElementById('processing-text');
        if (!stepEl) return;

        // Reset icon back to sparkle for processing phase
        var icon = document.querySelector('.processing-icon');
        if (icon) {
            icon.textContent = '\u2728';
            icon.style.fontSize = '';
        }

        var messages = {
            compositing: 'Composing your masterpiece...',
            applying_effect: 'Applying the magic...',
            uploading: 'Uploading to gallery...',
            done: 'Almost there...',
        };

        if (textEl && messages[step]) {
            textEl.textContent = messages[step];
        }

        if (frame && totalFrames) {
            stepEl.textContent = 'Frame ' + frame + ' of ' + totalFrames;
        } else {
            stepEl.textContent = '';
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

        if (msg.cloud_gallery_url) {
            // Cloud gallery available — generate QR pointing to the cloud URL
            var qr = document.getElementById('qr-code');
            if (qr) qr.src = '/api/share/qr?url=' + encodeURIComponent(msg.cloud_gallery_url);
            var reviewQr = document.getElementById('review-qr-img');
            if (reviewQr) reviewQr.src = '/api/share/qr?url=' + encodeURIComponent(msg.cloud_gallery_url);
        } else if (msg.qr_url) {
            var qr = document.getElementById('qr-code');
            if (qr) qr.src = msg.qr_url;
            // Also show QR on review screen
            var reviewQr = document.getElementById('review-qr-img');
            if (reviewQr) reviewQr.src = msg.qr_url;
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
        var self = this;
        if (target === 'thankyou') {
            this.send('done');
        } else if (target === 'idle') {
            this.send('auto_idle');
            // Force UI to idle after 2s even if server doesn't respond
            setTimeout(function () {
                if (self.state !== 'idle') {
                    self.showState('idle');
                }
            }, 2000);
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
    /*  Floating photo slideshow (idle attract mode)                       */
    /* ------------------------------------------------------------------ */

    startSlideshow() {
        var vignette = document.getElementById('slideshow-vignette');
        if (vignette) vignette.style.display = '';
        this.loadSlidePhotos();
        this._lastCycledCard = -1;
        this.slideshowTimer = setInterval(() => this.cycleSlidePhoto(), 5000);
        this.loadPhotoCounter();
    }

    async loadSlidePhotos() {
        try {
            var res = await fetch('/api/gallery/?limit=20');
            var data = await res.json();
            this.slidePhotos = data.photos || [];
            if (this.slidePhotos.length > 0) {
                this.initFloatingCards();
            }
        } catch (e) {
            console.warn('[booth] slideshow fetch failed:', e);
        }
    }

    initFloatingCards() {
        var container = document.getElementById('slideshow-float');
        if (!container || this.slidePhotos.length === 0) return;
        container.innerHTML = '';

        // Force container above sections (sections are z-index:0/1)
        container.style.cssText = 'position:fixed;inset:0;overflow:hidden;z-index:5;pointer-events:none;';

        // Random positions but no overlap — divide screen into zones
        var cardCount = Math.min(4, this.slidePhotos.length);
        this._floatCards = [];
        var placed = []; // Track placed card positions

        for (var i = 0; i < cardCount; i++) {
            var card = document.createElement('div');

            // Keep trying random positions until no overlap
            var x, y, attempts = 0;
            do {
                x = Math.random() * 75 + 3;
                y = Math.random() * 70 + 5;
                attempts++;
                var overlaps = false;
                for (var p = 0; p < placed.length; p++) {
                    if (Math.abs(x - placed[p].x) < 28 && Math.abs(y - placed[p].y) < 30) {
                        overlaps = true;
                        break;
                    }
                }
            } while ((overlaps || (x > 25 && x < 65 && y > 25 && y < 65)) && attempts < 50);
            placed.push({ x: x, y: y });

            var rot = (Math.random() * 20 - 10);
            // ALL inline styles — no CSS classes needed
            card.style.cssText = 'position:absolute;width:200px;border-radius:8px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.4);border:3px solid rgba(255,255,255,0.15);opacity:0.7;left:' + x + '%;top:' + y + '%;transform:rotate(' + rot + 'deg);transition:opacity 1s;';

            var img = document.createElement('img');
            var photo = this.slidePhotos[i % this.slidePhotos.length];
            var isGif = photo.photo_path && photo.photo_path.endsWith('.gif');
            img.src = '/api/gallery/' + photo.id + (isGif ? '' : '/thumbnail');
            img.alt = '';
            img.style.cssText = 'width:100%;display:block;';
            card.appendChild(img);

            container.appendChild(card);
            this._floatCards.push({ el: card, index: i });

            // Stagger the fade-in
            setTimeout(function (c) { c.classList.add('visible'); }, i * 500, card);
        }
    }

    _findOpenSpot(placed) {
        var x, y, attempts = 0;
        do {
            x = Math.random() * 75 + 3;
            y = Math.random() * 70 + 5;
            attempts++;
            var overlaps = false;
            for (var p = 0; p < placed.length; p++) {
                if (Math.abs(x - placed[p].x) < 28 && Math.abs(y - placed[p].y) < 30) {
                    overlaps = true;
                    break;
                }
            }
        } while ((overlaps || (x > 25 && x < 65 && y > 25 && y < 65)) && attempts < 50);
        return { x: x, y: y };
    }

    cycleSlidePhoto() {
        if (!this._floatCards || this._floatCards.length === 0 || this.slidePhotos.length <= 1) return;

        // Don't pick the same card twice in a row
        var cardIdx;
        do {
            cardIdx = Math.floor(Math.random() * this._floatCards.length);
        } while (cardIdx === this._lastCycledCard && this._floatCards.length > 1);
        this._lastCycledCard = cardIdx;
        var card = this._floatCards[cardIdx];
        var photoIdx = Math.floor(Math.random() * this.slidePhotos.length);
        var photo = this.slidePhotos[photoIdx];

        // Get positions of OTHER cards (not the one we're moving)
        var otherPositions = [];
        for (var i = 0; i < this._floatCards.length; i++) {
            if (i !== cardIdx) {
                otherPositions.push({
                    x: parseFloat(this._floatCards[i].el.style.left),
                    y: parseFloat(this._floatCards[i].el.style.top),
                });
            }
        }

        // Fade out
        card.el.style.opacity = '0';
        var newPos = this._findOpenSpot(otherPositions);
        var newRot = (Math.random() * 20 - 10);
        // Wait for fade out to complete
        setTimeout(function () {
            // Move while invisible (no transition)
            card.el.style.transition = 'none';
            card.el.style.left = newPos.x + '%';
            card.el.style.top = newPos.y + '%';
            card.el.style.transform = 'rotate(' + newRot + 'deg)';
            // Swap image and wait for it to load before fading in
            var img = card.el.querySelector('img');
            var isGif = photo.photo_path && photo.photo_path.endsWith('.gif');
            var newSrc = '/api/gallery/' + photo.id + (isGif ? '' : '/thumbnail');
            var fadeIn = function () {
                void card.el.offsetWidth;
                card.el.style.transition = 'opacity 1s';
                card.el.style.opacity = '0.7';
            };
            if (img) {
                img.onload = fadeIn;
                img.onerror = fadeIn;
                img.src = newSrc;
                // Fallback if image is cached (onload won't fire)
                if (img.complete) fadeIn();
            }
        }, 1200);
    }

    stopSlideshow() {
        if (this.slideshowTimer) {
            clearInterval(this.slideshowTimer);
            this.slideshowTimer = null;
        }
        var container = document.getElementById('slideshow-float');
        if (container) container.innerHTML = '';
        var vignette = document.getElementById('slideshow-vignette');
        if (vignette) vignette.style.display = 'none';
        this._floatCards = [];
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
    /*  Effect picker                                                      */
    /* ------------------------------------------------------------------ */

    showEffectPicker() {
        document.getElementById('effect-picker').style.display = 'flex';
    }

    hideEffectPicker() {
        document.getElementById('effect-picker').style.display = 'none';
    }

    showPerShotEffectPicker() {
        // For multi-shot: show effect picker overlay on the preview screen
        var picker = document.getElementById('effect-picker');
        var previewSection = document.querySelector('[data-state="preview"]');
        if (picker && previewSection) {
            // Update heading for between-shots context
            var heading = picker.querySelector('h2');
            if (heading) heading.textContent = 'Change effect or strike a new pose!';
            previewSection.appendChild(picker);
            picker.style.display = 'flex';
            this._perShotPicking = true;
            // Auto-dismiss after 5 seconds — use the last selected effect
            var self = this;
            this._perShotTimer = setTimeout(function () {
                if (self._perShotPicking) {
                    self.onPerShotEffectPicked(self.selectedEffect || 'none');
                }
            }, 5000);
        }
    }

    onPerShotEffectPicked(effect) {
        // Clear auto-dismiss timer
        if (this._perShotTimer) {
            clearTimeout(this._perShotTimer);
            this._perShotTimer = null;
        }
        // Store the effect for this capture
        this.send('select_per_shot_effect', { effect: effect });
        // Move picker back to choose section and hide
        var picker = document.getElementById('effect-picker');
        var chooseSection = document.querySelector('[data-state="choose"]');
        if (picker && chooseSection) {
            // Restore heading
            var heading = picker.querySelector('h2');
            if (heading) heading.textContent = this.i18n.t('pick_effect');
            chooseSection.appendChild(picker);
            picker.style.display = 'none';
        }
        this._perShotPicking = false;
        this.selectedEffect = effect;
        // Start countdown for next capture
        this.startCountdown();
    }

    /* ------------------------------------------------------------------ */
    /*  Background picker (chromakey)                                      */
    /* ------------------------------------------------------------------ */

    async showBackgroundPicker() {
        var picker = document.getElementById('bg-picker');
        var grid = document.getElementById('bg-grid');
        if (!picker || !grid) return;

        // Fetch available backgrounds
        try {
            var res = await fetch('/api/admin/backgrounds');
            var data = await res.json();
            var backgrounds = data.backgrounds || [];
        } catch (e) {
            console.warn('[booth] Failed to load backgrounds:', e);
            // Fall through without chromakey
            this.selectedBackground = null;
            this.send('choose', {
                mode: this.pendingMode,
                template: this.pendingTemplate,
                effect: this.selectedEffect,
            });
            return;
        }

        if (backgrounds.length === 0) {
            // No backgrounds available, proceed without
            this.selectedBackground = null;
            this.send('choose', {
                mode: this.pendingMode,
                template: this.pendingTemplate,
                effect: this.selectedEffect,
            });
            return;
        }

        grid.innerHTML = '';
        var self = this;

        for (var i = 0; i < backgrounds.length; i++) {
            (function(bg) {
                var card = document.createElement('div');
                card.className = 'bg-card';

                var img = document.createElement('img');
                img.src = '/static/backgrounds/' + bg;
                img.alt = bg;
                img.loading = 'lazy';
                card.appendChild(img);

                var label = document.createElement('span');
                // Format name: remove extension, replace dashes with spaces
                label.textContent = bg.replace(/\.[^.]+$/, '').replace(/-/g, ' ');
                card.appendChild(label);

                card.addEventListener('click', function() {
                    if (self.sounds) self.sounds.play('click');
                    self.onBackgroundPicked(bg);
                });

                grid.appendChild(card);
            })(backgrounds[i]);
        }

        picker.style.display = 'flex';
    }

    hideBackgroundPicker() {
        var picker = document.getElementById('bg-picker');
        if (picker) picker.style.display = 'none';
    }

    onBackgroundPicked(background) {
        this.selectedBackground = background;
        this.hideBackgroundPicker();
        this.send('choose', {
            mode: this.pendingMode,
            template: this.pendingTemplate,
            effect: this.selectedEffect,
            background: background,
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Template picker                                                    */
    /* ------------------------------------------------------------------ */

    async showTemplatePicker(mode) {
        this._pendingMode = mode;

        // Determine which slot counts are valid for this mode
        var validSlots;
        if (mode === 'gif' || mode === 'boomerang') {
            validSlots = [1]; // GIF/boomerang always single
        } else if (mode === 'photo') {
            // "single" mode = 1 slot, "multi" = 2+ slots
            var isSingle = (this.pendingTemplate === 'single');
            validSlots = isSingle ? [1] : null; // null = 2+ slots
        } else {
            validSlots = null;
        }

        var res = await fetch('/api/admin/templates');
        var data = await res.json();
        var self = this;

        // Load all templates and filter
        var matching = [];
        for (var i = 0; i < data.templates.length; i++) {
            var tplRes = await fetch('/api/admin/templates/' + data.templates[i]);
            var tpl = await tplRes.json();
            tpl._name = data.templates[i];
            var slots = tpl.slots ? tpl.slots.length : 1;
            if (validSlots === null) {
                if (slots >= 2) matching.push(tpl);
            } else if (validSlots.indexOf(slots) !== -1) {
                matching.push(tpl);
            }
        }

        // If only 1 matching template, skip picker
        if (matching.length <= 1) {
            this.pendingTemplate = matching.length ? matching[0]._name : 'single';
            this.showEffectPicker();
            return;
        }

        var grid = document.getElementById('template-picker-grid');
        grid.innerHTML = '';

        for (var j = 0; j < matching.length; j++) {
            (function (tpl) {
                var name = tpl._name;
                var card = document.createElement('button');
                card.className = 'template-card';
                card.dataset.template = name;

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
                label.textContent = name.replace(/-/g, ' ').replace('4x6', '').trim();
                card.appendChild(label);

                card.addEventListener('click', function () {
                    if (self.sounds) self.sounds.play('click');
                    self.pendingTemplate = name;
                    document.getElementById('template-picker').style.display = 'none';
                    document.querySelector('.choose-grid').style.display = '';
                    self.showEffectPicker();
                });

                grid.appendChild(card);
            })(matching[j]);
        }

        // Show picker, hide mode chooser
        document.querySelector('.choose-grid').style.display = 'none';
        document.querySelector('[data-state="choose"] .section-heading').style.display = 'none';
        document.getElementById('template-picker').style.display = '';
    }

    resetChooseScreen() {
        // Reset effect picker, background picker, and template picker when re-entering choose
        this.hideEffectPicker();
        this.hideBackgroundPicker();
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
        clearTimeout(this._warningTimer);
        if (this.state !== 'idle' && this.state !== 'processing' && this.state !== 'capture') {
            var self = this;
            // Show warning after 90 seconds
            this._warningTimer = setTimeout(function () {
                self.showError('Still there? Tap or press a button!');
            }, 90000);
            // Force reset after 120 seconds
            this.safetyTimer = setTimeout(function () {
                console.warn('[booth] Safety timeout — returning to idle');
                self.send('cancel');
                setTimeout(function () {
                    if (self.state !== 'idle') {
                        self.showState('idle');
                    }
                }, 3000);
            }, 120000);
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

        // Hide button hints when touch is used (touch users don't need them)
        document.addEventListener('touchstart', function () {
            var hints = document.getElementById('button-hints');
            if (hints) hints.style.display = 'none';
        });

        // Processing cancel: force back to idle even if server is stuck
        var procCancel = document.getElementById('processing-cancel-btn');
        if (procCancel) {
            procCancel.addEventListener('click', function () {
                self.send('cancel');
                // Force UI to idle after 1 second regardless
                setTimeout(function () {
                    self.showState('idle');
                    window.location.reload();
                }, 1000);
            });
        }

        // Thankyou: tap anywhere to go back to idle
        var thankyou = document.getElementById('thankyou-section');
        if (thankyou) {
            thankyou.addEventListener('click', function () {
                self.send('auto_idle');
            });
        }

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
                    var template = btn.dataset.template || 'single';

                    self.pendingMode = mode;
                    self.pendingTemplate = template;

                    // "multi" = show multi-slot templates
                    // Always show template picker
                    self.showTemplatePicker(mode);
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




        // Effect picker back button
        var effectBack = document.getElementById('effect-back-btn');
        if (effectBack) {
            effectBack.addEventListener('click', function () {
                if (self._perShotPicking) {
                    // During multi-shot, back just dismisses and uses last effect
                    self.onPerShotEffectPicked(self.selectedEffect || 'none');
                } else {
                    // Go back to mode selection
                    self.hideEffectPicker();
                    self.resetChooseScreen();
                }
            });
        }

        // Background picker back button
        var bgBack = document.getElementById('bg-back-btn');
        if (bgBack) {
            bgBack.addEventListener('click', function () {
                self.hideBackgroundPicker();
                self.showEffectPicker();
            });
        }

        // Effect picker card clicks
        var effectCards = document.querySelectorAll('.effect-card');
        for (var e = 0; e < effectCards.length; e++) {
            (function(card) {
                card.addEventListener('click', function() {
                    if (self.sounds) self.sounds.play('click');
                    var effect = card.dataset.effect;
                    self.selectedEffect = effect;

                    if (self._perShotPicking) {
                        // Per-shot effect pick (multi-shot between captures)
                        self.onPerShotEffectPicked(effect);
                    } else {
                        // Initial effect pick before first capture
                        self.hideEffectPicker();
                        self._isGifMode = (self.pendingMode === 'gif' || self.pendingMode === 'boomerang');
                        self._multiShotActive = (self.pendingTemplate === 'multi' || (self.pendingTemplate && self.pendingTemplate !== 'single' && self.pendingTemplate !== 'polaroid-4x6'));

                        // If chromakey enabled, show background picker before starting
                        if (self.wsConfig && self.wsConfig.chromakey_enabled) {
                            self.showBackgroundPicker();
                        } else {
                            self.selectedBackground = null;
                            self.send('choose', {
                                mode: self.pendingMode,
                                template: self.pendingTemplate,
                                effect: effect,
                            });
                        }
                    }
                });
            })(effectCards[e]);
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
