/* Admin Panel JavaScript */

class AdminPanel {
    constructor() {
        this.currentTab = 'system';
        this.config = null;
    }

    async init() {
        // Check if authentication is required
        try {
            var res = await fetch('/api/admin/system');
            if (res.status === 401) {
                this.showLogin();
                return;
            }
        } catch (e) {
            // Network error -- proceed anyway
        }

        this.hideLogin();
        this.bindTabs();
        this.showTab('system');
    }

    showLogin() {
        var overlay = document.getElementById('admin-login-overlay');
        overlay.classList.add('visible');

        var passwordInput = document.getElementById('admin-password');
        var loginBtn = document.getElementById('admin-login-btn');
        var errorEl = document.getElementById('login-error');

        // Clear previous state
        passwordInput.value = '';
        errorEl.style.display = 'none';

        // Remove old listeners by cloning
        var newBtn = loginBtn.cloneNode(true);
        loginBtn.parentNode.replaceChild(newBtn, loginBtn);

        var newInput = passwordInput.cloneNode(true);
        passwordInput.parentNode.replaceChild(newInput, passwordInput);

        newBtn.addEventListener('click', () => this.doLogin());
        newInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.doLogin();
        });

        newInput.focus();
    }

    hideLogin() {
        document.getElementById('admin-login-overlay').classList.remove('visible');
    }

    async doLogin() {
        var password = document.getElementById('admin-password').value;
        var errorEl = document.getElementById('login-error');
        errorEl.style.display = 'none';

        try {
            var res = await fetch('/api/admin/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: password}),
            });
            if (res.ok) {
                this.hideLogin();
                this.bindTabs();
                this.showTab('system');
            } else {
                errorEl.style.display = '';
                document.getElementById('admin-password').focus();
            }
        } catch (e) {
            errorEl.textContent = 'Connection error';
            errorEl.style.display = '';
        }
    }

    bindTabs() {
        document.querySelectorAll('[data-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                this.currentTab = tab.dataset.tab;
                this.showTab(this.currentTab);
            });
        });
    }

    showTab(name) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('[data-tab]').forEach(t => t.classList.remove('active'));
        document.querySelector(`.tab-content[data-content="${name}"]`)?.classList.add('active');
        document.querySelector(`[data-tab="${name}"]`)?.classList.add('active');

        if (name === 'system') this.loadSystemInfo();
        if (name === 'camera') this.loadCameraFraming();
        if (name === 'config') this.loadConfig();
        if (name === 'gallery') this.loadGallery();
        if (name === 'theme') this.loadTheme();
        if (name === 'events') this.loadEvents();
        if (name === 'templates') this.loadTemplates();
        if (name === 'analytics') this.loadAnalytics();
    }

    /* ── System Tab ─────────────────────────────────────────────── */

    async loadSystemInfo() {
        const container = document.getElementById('system-content');
        container.innerHTML = '<div class="loading">Loading system info...</div>';

        try {
            const [sysRes, connRes] = await Promise.all([
                fetch('/api/admin/system'),
                fetch('/api/admin/connection'),
            ]);
            const info = await sysRes.json();
            const conn = await connRes.json();
            this.renderSystemTab(info, conn);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load system info: ${e.message}</div>`;
        }
    }

    renderSystemTab(info, conn) {
        const container = document.getElementById('system-content');

        const statusDot = (ok) => ok
            ? '<span class="status-dot status-ok"></span>'
            : '<span class="status-dot status-err"></span>';

        const diskPct = info.disk
            ? Math.round((info.disk.used_gb / info.disk.total_gb) * 100)
            : 0;
        const memPct = info.memory ? info.memory.percent : 0;

        container.innerHTML = `
            <div class="cards">
                <div class="card">
                    <h3>Hardware</h3>
                    <div class="card-row">${statusDot(info.camera?.available)} Camera: ${info.camera?.available ? info.camera.type : 'Not detected'}</div>
                    <div class="card-row">${statusDot(info.printer?.available)} Printer: ${info.printer?.available ? info.printer.name : 'Not available'}</div>
                    <div class="card-row">${statusDot(info.gpio?.available)} GPIO: ${info.gpio?.available ? 'Connected' : 'Not available'}</div>
                </div>
                <div class="card">
                    <h3>System</h3>
                    <div class="card-row">Platform: ${info.platform}</div>
                    <div class="card-row">Python: ${info.python}</div>
                    <div class="card-row">Hostname: ${info.hostname}</div>
                    <div class="card-row">IP: ${info.ip}</div>
                    <div class="card-row">Photos: ${info.photo_count}</div>
                </div>
                <div class="card">
                    <h3>Disk</h3>
                    <div class="progress-bar"><div class="progress-fill" style="width:${diskPct}%"></div></div>
                    <div class="card-row">${info.disk ? `${info.disk.used_gb} / ${info.disk.total_gb} GB (${info.disk.free_gb} GB free)` : 'N/A'}</div>
                </div>
                <div class="card">
                    <h3>Memory</h3>
                    <div class="progress-bar"><div class="progress-fill" style="width:${memPct}%"></div></div>
                    <div class="card-row">${info.memory ? `${info.memory.used_mb} / ${info.memory.total_mb} MB (${memPct}%)` : 'N/A'}</div>
                </div>
                <div class="card card-wide">
                    <h3>Connection URLs</h3>
                    <div class="card-row">
                        <strong>Booth:</strong> <a href="${conn.booth_url}" target="_blank">${conn.booth_url}</a>
                    </div>
                    <div class="card-row">
                        <strong>Admin:</strong> <a href="${conn.admin_url}" target="_blank">${conn.admin_url}</a>
                    </div>
                    <div class="qr-container" id="qr-booth"></div>
                </div>
            </div>
        `;

        // QR code generation (simple canvas-based via external lib or text fallback)
        this.renderQR('qr-booth', conn.booth_url);
    }

    renderQR(containerId, url) {
        const container = document.getElementById(containerId);
        if (!container) return;
        // Use a simple approach: render a link users can scan/copy
        container.innerHTML = `
            <div class="qr-placeholder">
                <div class="qr-label">Scan to open booth</div>
                <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(url)}"
                     alt="QR Code" width="180" height="180" loading="lazy"
                     onerror="this.parentElement.innerHTML='<code>${url}</code>'" />
            </div>
        `;
    }

    /* ── Camera Tab ─────────────────────────────────────────────── */

    async loadCameraFraming() {
        const container = document.getElementById('camera-content');
        container.innerHTML = '<div class="loading">Loading camera controls...</div>';

        try {
            const res = await fetch('/api/admin/camera/framing');
            this.framing = await res.json();
            this.renderCameraControls(this.framing);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load camera framing: ${e.message}</div>`;
        }
    }

    renderCameraControls(framing) {
        const container = document.getElementById('camera-content');

        container.innerHTML = `
            <div class="camera-framing-layout">
                <div>
                    <div class="camera-preview-wrap">
                        <img id="admin-camera-preview"
                             src="/api/camera/stream?${Date.now()}"
                             alt="Camera Preview"
                             class="${framing.mirror_preview ? 'mirrored' : ''}"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='';" />
                        <div style="display:none; color:#888; text-align:center; padding:3rem;">
                            No camera available
                        </div>
                    </div>
                </div>
                <div class="camera-controls-panel">
                    <div class="control-group">
                        <h4>Zoom</h4>
                        <div class="slider-field">
                            <label>
                                <span>Zoom Level</span>
                                <span id="zoom-value">${framing.zoom.toFixed(1)}x</span>
                            </label>
                            <input type="range" id="zoom-slider" min="1" max="4" step="0.1"
                                   value="${framing.zoom}"
                                   oninput="admin.onZoomChange(this.value)" />
                        </div>
                    </div>
                    <div class="control-group">
                        <h4>Pan / Crop</h4>
                        <div class="slider-field">
                            <label>
                                <span>Horizontal</span>
                                <span id="pan-x-value">${(framing.crop_x * 100).toFixed(0)}%</span>
                            </label>
                            <input type="range" id="pan-x-slider" min="0" max="100" step="1"
                                   value="${framing.crop_x * 100}"
                                   oninput="admin.onPanChange()" />
                        </div>
                        <div class="slider-field">
                            <label>
                                <span>Vertical</span>
                                <span id="pan-y-value">${(framing.crop_y * 100).toFixed(0)}%</span>
                            </label>
                            <input type="range" id="pan-y-slider" min="0" max="100" step="1"
                                   value="${framing.crop_y * 100}"
                                   oninput="admin.onPanChange()" />
                        </div>
                        <div class="slider-field">
                            <label>
                                <span>Width</span>
                                <span id="crop-w-value">${(framing.crop_width * 100).toFixed(0)}%</span>
                            </label>
                            <input type="range" id="crop-w-slider" min="10" max="100" step="1"
                                   value="${framing.crop_width * 100}"
                                   oninput="admin.onPanChange()" />
                        </div>
                        <div class="slider-field">
                            <label>
                                <span>Height</span>
                                <span id="crop-h-value">${(framing.crop_height * 100).toFixed(0)}%</span>
                            </label>
                            <input type="range" id="crop-h-slider" min="10" max="100" step="1"
                                   value="${framing.crop_height * 100}"
                                   oninput="admin.onPanChange()" />
                        </div>
                    </div>
                    <div class="control-group">
                        <h4>Mirror</h4>
                        <div class="toggle-row">
                            <span>Mirror Preview (selfie mode)</span>
                            <label class="toggle">
                                <input type="checkbox" id="mirror-preview" ${framing.mirror_preview ? 'checked' : ''}
                                       onchange="admin.onMirrorChange()" />
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        <div class="toggle-row">
                            <span>Mirror Capture (printed photo)</span>
                            <label class="toggle">
                                <input type="checkbox" id="mirror-capture" ${framing.mirror_capture ? 'checked' : ''}
                                       onchange="admin.onMirrorChange()" />
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                    <button class="btn btn-reset" onclick="admin.resetFraming()">Reset to Default</button>
                </div>
            </div>
        `;
    }

    async onZoomChange(value) {
        const zoom = parseFloat(value);
        document.getElementById('zoom-value').textContent = zoom.toFixed(1) + 'x';
        // Zoom = centered crop. Calculate crop values from zoom level.
        const cropW = 1.0 / zoom;
        const cropH = 1.0 / zoom;
        const cropX = (1.0 - cropW) / 2;
        const cropY = (1.0 - cropH) / 2;
        // Sync pan/crop sliders
        const els = {
            'pan-x-slider': cropX * 100, 'pan-y-slider': cropY * 100,
            'crop-w-slider': cropW * 100, 'crop-h-slider': cropH * 100,
        };
        for (const [id, val] of Object.entries(els)) {
            const el = document.getElementById(id);
            if (el) el.value = val;
        }
        document.getElementById('pan-x-value').textContent = (cropX * 100).toFixed(0) + '%';
        document.getElementById('pan-y-value').textContent = (cropY * 100).toFixed(0) + '%';
        document.getElementById('crop-w-value').textContent = (cropW * 100).toFixed(0) + '%';
        document.getElementById('crop-h-value').textContent = (cropH * 100).toFixed(0) + '%';
        await this.updateFraming({ crop_x: cropX, crop_y: cropY, crop_width: cropW, crop_height: cropH });
    }

    async onPanChange() {
        const cropX = parseFloat(document.getElementById('pan-x-slider').value) / 100;
        const cropY = parseFloat(document.getElementById('pan-y-slider').value) / 100;
        const cropW = parseFloat(document.getElementById('crop-w-slider').value) / 100;
        const cropH = parseFloat(document.getElementById('crop-h-slider').value) / 100;

        document.getElementById('pan-x-value').textContent = (cropX * 100).toFixed(0) + '%';
        document.getElementById('pan-y-value').textContent = (cropY * 100).toFixed(0) + '%';
        document.getElementById('crop-w-value').textContent = (cropW * 100).toFixed(0) + '%';
        document.getElementById('crop-h-value').textContent = (cropH * 100).toFixed(0) + '%';

        await this.updateFraming({
            crop_x: cropX,
            crop_y: cropY,
            crop_width: cropW,
            crop_height: cropH,
        });
    }

    async onMirrorChange() {
        const mirrorPreview = document.getElementById('mirror-preview').checked;
        const mirrorCapture = document.getElementById('mirror-capture').checked;

        // Apply CSS mirror immediately for zero-latency feedback
        const preview = document.getElementById('admin-camera-preview');
        if (preview) {
            preview.classList.toggle('mirrored', mirrorPreview);
        }

        await this.updateFraming({
            mirror_preview: mirrorPreview,
            mirror_capture: mirrorCapture,
        });
    }

    async updateFraming(data) {
        try {
            const res = await fetch('/api/admin/camera/framing', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                this.showNotification('Failed to update framing', 'error');
            }
        } catch (e) {
            this.showNotification(`Framing update failed: ${e.message}`, 'error');
        }
    }

    async resetFraming() {
        await this.updateFraming({
            crop_x: 0.0,
            crop_y: 0.0,
            crop_width: 1.0,
            crop_height: 1.0,
            zoom: 1.0,
            mirror_preview: true,
            mirror_capture: false,
        });
        this.showNotification('Camera framing reset to default', 'success');
        this.loadCameraFraming();
    }

    /* ── Config Tab ──────────────────────────────────────────────── */

    async loadConfig() {
        const container = document.getElementById('config-content');
        container.innerHTML = '<div class="loading">Loading configuration...</div>';

        try {
            const res = await fetch('/api/admin/config');
            this.config = await res.json();
            this.renderConfigForm(this.config);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load config: ${e.message}</div>`;
        }
    }

    renderConfigForm(config) {
        const container = document.getElementById('config-content');
        this.config = config;

        // Helpers for building fields
        const toggle = (section, key, label, desc, checked) => `
            <div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">${label}</div>
                    ${desc ? `<div class="config-field-desc">${desc}</div>` : ''}
                </div>
                <div class="config-field-control">
                    <label class="cfg-toggle">
                        <input type="checkbox" ${checked ? 'checked' : ''}
                               data-section="${section}" data-key="${key}"
                               onchange="admin.patchConfigField('${section}', '${key}', this.checked)" />
                        <span class="cfg-toggle-slider"></span>
                    </label>
                </div>
            </div>`;

        const textInput = (section, key, label, desc, value, cls = '') => `
            <div class="config-field${cls.includes('stacked') ? ' stacked' : ''}">
                <div class="config-field-info">
                    <div class="config-field-label">${label}</div>
                    ${desc ? `<div class="config-field-desc">${desc}</div>` : ''}
                </div>
                <div class="config-field-control">
                    <input type="text" class="config-input ${cls}" value="${this.escAttr(value)}"
                           data-section="${section}" data-key="${key}"
                           onchange="admin.patchConfigField('${section}', '${key}', this.value)" />
                </div>
            </div>`;

        const numberInput = (section, key, label, desc, value, cls = 'config-input-sm') => `
            <div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">${label}</div>
                    ${desc ? `<div class="config-field-desc">${desc}</div>` : ''}
                </div>
                <div class="config-field-control">
                    <input type="number" class="config-input ${cls}" value="${value}"
                           data-section="${section}" data-key="${key}"
                           onchange="admin.patchConfigField('${section}', '${key}', Number(this.value))" />
                </div>
            </div>`;

        const selectInput = (section, key, label, desc, value, options) => {
            const opts = options.map(o => {
                const val = typeof o === 'object' ? o.value : o;
                const lbl = typeof o === 'object' ? o.label : o;
                return `<option value="${val}" ${val === value ? 'selected' : ''}>${lbl}</option>`;
            }).join('');
            return `
            <div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">${label}</div>
                    ${desc ? `<div class="config-field-desc">${desc}</div>` : ''}
                </div>
                <div class="config-field-control">
                    <select class="config-select"
                            data-section="${section}" data-key="${key}"
                            onchange="admin.patchConfigField('${section}', '${key}', this.value)">
                        ${opts}
                    </select>
                </div>
            </div>`;
        };

        const slider = (section, key, label, desc, value, min, max, step, suffix = '') => `
            <div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">${label}</div>
                    ${desc ? `<div class="config-field-desc">${desc}</div>` : ''}
                </div>
                <div class="config-field-control">
                    <div class="slider-control">
                        <input type="range" min="${min}" max="${max}" step="${step}" value="${value}"
                               data-section="${section}" data-key="${key}"
                               oninput="this.nextElementSibling.textContent = this.value + '${suffix}'; admin.patchConfigFieldDebounced('${section}', '${key}', Number(this.value))" />
                        <span class="slider-value">${value}${suffix}</span>
                    </div>
                </div>
            </div>`;

        const sectionCard = (title, desc, content) => `
            <div class="config-section">
                <h3>${title}</h3>
                <div class="section-desc">${desc}</div>
                ${content}
            </div>`;

        const c = config;

        // Languages
        const languages = [
            { value: 'en', label: 'English' },
            { value: 'de', label: 'Deutsch' },
            { value: 'fr', label: 'Francais' },
            { value: 'es', label: 'Espanol' },
            { value: 'it', label: 'Italiano' },
            { value: 'pt', label: 'Portugues' },
            { value: 'nl', label: 'Nederlands' },
            { value: 'ja', label: 'Japanese' },
            { value: 'zh', label: 'Chinese' },
        ];

        // Effects
        const effects = (c.picture?.available_effects || []).map(e => ({
            value: e,
            label: e === 'none' ? 'None (Original)' : this.formatLabel(e),
        }));

        // Build sections

        // 1. Event Setup
        const eventSetupHtml = sectionCard('Event Setup',
            'Configure the basics for your event. This is the first thing to set up when running a new event.',
            textInput('sharing', 'event_name', 'Event Name', 'Displayed on QR share pages and photo footers', c.sharing?.event_name || '', 'config-input-lg') +
            selectInput('general', 'language', 'Language', 'Interface language for the booth screen', c.general?.language || 'en', languages) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Event Logo</div>
                    <div class="config-field-desc">Displayed on the idle screen and optionally on prints</div>
                </div>
                <div class="config-field-control">
                    <div class="logo-thumb" id="cfg-logo-thumb">
                        <span class="placeholder">No logo</span>
                    </div>
                    <a href="#" onclick="document.querySelector('[data-tab=\\'theme\\']').click(); return false;"
                       style="font-size:0.85rem; margin-left:0.5rem;">Upload in Theme tab</a>
                </div>
            </div>` +
            textInput('branding', 'company_name', 'Company Name', 'Optional branding name displayed on booth', c.branding?.company_name || '', 'config-input-md') +
            textInput('branding', 'tagline', 'Tagline', 'Shown below the company name on idle screen', c.branding?.tagline || '', 'config-input-md')
        );

        // 2. Camera
        const camRes = c.camera?.preview_resolution || [1280, 720];
        const cameraHtml = sectionCard('Camera',
            'Camera hardware settings. Use the Camera tab for live framing, zoom, and crop adjustments.',
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Live Preview</div>
                    <div class="config-field-desc">Preview resolution: ${camRes[0]}x${camRes[1]}</div>
                </div>
                <div class="config-field-control">
                    <div class="camera-thumb ${c.camera?.mirror_preview ? 'mirrored' : ''}" id="cfg-camera-thumb">
                        <img src="/api/camera/stream?t=${Date.now()}" alt="Preview"
                             onerror="this.style.display='none'; this.parentElement.innerHTML='<span class=\\'placeholder\\'>No camera</span>'" />
                    </div>
                </div>
            </div>` +
            toggle('camera', 'mirror_preview', 'Mirror Preview', 'Selfie-mode: flip the live preview horizontally', c.camera?.mirror_preview) +
            toggle('camera', 'mirror_capture', 'Mirror Capture', 'Also flip the saved/printed photo', c.camera?.mirror_capture) +
            selectInput('camera', 'backend', 'Camera Backend', 'Hybrid = USB webcam for smooth preview + Pi camera for high-res captures', c.camera?.backend || 'auto', [
                { value: 'auto', label: 'Auto Detect' },
                { value: 'hybrid', label: 'Hybrid (USB preview + Pi capture)' },
                { value: 'picamera2', label: 'Pi Camera (picamera2)' },
                { value: 'webcam', label: 'USB Webcam (OpenCV)' },
                { value: 'gphoto2', label: 'DSLR (gPhoto2)' },
            ]) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Framing & Zoom</div>
                    <div class="config-field-desc">Fine-tune crop, zoom, and pan in the dedicated Camera tab</div>
                </div>
                <div class="config-field-control">
                    <a href="#" class="btn btn-sm" style="background:#f5f5ff; color:#6c63ff; border:1px solid #d0d0e8;"
                       onclick="document.querySelector('[data-tab=\\'camera\\']').click(); return false;">Open Camera Controls</a>
                </div>
            </div>`
        );

        // 3. Photo Settings
        const photoSettingsHtml = sectionCard('Photo Settings',
            'Configure how photos are captured, processed, and laid out on the final print.',
            numberInput('picture', 'capture_count', 'Capture Count', 'Number of photos per session', c.picture?.capture_count || 4) +
            selectInput('picture', 'default_effect', 'Default Effect', 'Applied to all captures unless guest changes it', c.picture?.default_effect || 'none', effects) +
            toggle('picture', 'guest_picks_template', 'Guest Picks Template', 'Let guests choose their print layout before capturing', c.picture?.guest_picks_template) +
            selectInput('picture', 'orientation', 'Orientation', 'Photo strip orientation', c.picture?.orientation || 'portrait', [
                { value: 'portrait', label: 'Portrait' },
                { value: 'landscape', label: 'Landscape' },
            ]) +
            textInput('picture', 'layout_template', 'Layout Template', 'Name of the print layout template to use', c.picture?.layout_template || 'classic-4x6', 'config-input-md') +
            textInput('picture', 'footer_text', 'Footer Text', 'Use {event_name} and {date} as placeholders', c.picture?.footer_text || '', 'config-input-md') +
            numberInput('picture', 'dpi', 'Print DPI', 'Resolution for printed photos (300 or 600)', c.picture?.dpi || 600) +
            `<div class="config-field stacked">
                <div class="config-field-info">
                    <div class="config-field-label">Pose Prompts</div>
                    <div class="config-field-desc">Text shown before each capture to guide guests</div>
                </div>
                <div class="config-field-control">
                    <div class="prompts-list" id="pose-prompts-editor">
                        ${(c.picture?.pose_prompts || []).map((p, i) => `
                            <div class="prompt-row">
                                <input type="text" value="${this.escAttr(p)}" data-index="${i}"
                                       onchange="admin.updatePosePrompt(${i}, this.value)" />
                                <button type="button" class="btn-remove-prompt" onclick="admin.removePosePrompt(${i})">&times;</button>
                            </div>
                        `).join('')}
                        <button type="button" class="btn-add-prompt" onclick="admin.addPosePrompt()">+ Add prompt</button>
                    </div>
                </div>
            </div>`
        );

        // 4. Sharing
        const sharingHtml = sectionCard('Sharing',
            'QR code sharing lets guests download their photos on their phones.',
            toggle('sharing', 'enabled', 'Enable QR Sharing', 'Show a QR code after each session for instant download', c.sharing?.enabled) +
            numberInput('sharing', 'qr_size', 'QR Code Size', 'Size in pixels of the generated QR code', c.sharing?.qr_size || 200) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Base URL</div>
                    <div class="config-field-desc">Auto-detected from server. Set manually if behind a proxy.</div>
                </div>
                <div class="config-field-control">
                    <input type="text" class="config-input config-input-md" value="${this.escAttr(c.sharing?.base_url || '')}"
                           placeholder="Auto-detect"
                           data-section="sharing" data-key="base_url"
                           onchange="admin.patchConfigField('sharing', 'base_url', this.value)" />
                </div>
            </div>`
        );

        // 5. Sound
        const volumePct = Math.round((c.sound?.volume || 0.8) * 100);
        const soundHtml = sectionCard('Sound',
            'Sound effects for the countdown, shutter, and other booth actions.',
            toggle('sound', 'enabled', 'Enable Sounds', 'Play sound effects during booth operation', c.sound?.enabled) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Volume</div>
                    <div class="config-field-desc">Master volume for all sound effects</div>
                </div>
                <div class="config-field-control">
                    <div class="slider-control">
                        <input type="range" min="0" max="100" step="5" value="${volumePct}"
                               oninput="this.nextElementSibling.textContent = this.value + '%'; admin.patchConfigFieldDebounced('sound', 'volume', Number(this.value) / 100)" />
                        <span class="slider-value">${volumePct}%</span>
                    </div>
                </div>
            </div>` +
            textInput('sound', 'countdown_beep', 'Countdown Beep', 'Sound file path for countdown', c.sound?.countdown_beep || '', 'config-input-md') +
            textInput('sound', 'shutter', 'Shutter Sound', 'Played when photo is captured', c.sound?.shutter || '', 'config-input-md') +
            textInput('sound', 'applause', 'Applause Sound', 'Played after session completes', c.sound?.applause || '', 'config-input-md')
        );

        // 6. Display
        const displayHtml = sectionCard('Display',
            'Screen and kiosk display settings for the booth monitor.',
            toggle('display', 'fullscreen', 'Fullscreen', 'Run the booth UI in fullscreen kiosk mode', c.display?.fullscreen) +
            slider('display', 'idle_timeout', 'Idle Timeout', 'Seconds before returning to the idle screen', c.display?.idle_timeout || 60, 10, 300, 5, 's') +
            toggle('display', 'hide_cursor', 'Hide Cursor', 'Hide the mouse cursor on the booth display', c.display?.hide_cursor) +
            numberInput('display', 'width', 'Screen Width', 'Display width in pixels', c.display?.width || 1024) +
            numberInput('display', 'height', 'Screen Height', 'Display height in pixels', c.display?.height || 600)
        );

        // 7. Network
        const networkHtml = sectionCard('Network',
            'Hotspot configuration for guest access.',
            toggle('network', 'hotspot_enabled', 'Enable Hotspot', 'Create a WiFi hotspot for guests to connect', c.network?.hotspot_enabled) +
            textInput('network', 'hotspot_ssid', 'Hotspot SSID', 'WiFi network name', c.network?.hotspot_ssid || 'PhotoBooth', 'config-input-md') +
            textInput('network', 'hotspot_password', 'Hotspot Password', 'WiFi password for guests', c.network?.hotspot_password || '', 'config-input-md')
        );

        // 8. Printing
        const printingHtml = sectionCard('Printing',
            'Configure the connected printer for instant photo prints.',
            toggle('printer', 'enabled', 'Enable Printing', 'Allow photos to be printed from the booth', c.printer?.enabled) +
            textInput('printer', 'printer_name', 'Printer Name', 'CUPS printer name. Leave empty for default.', c.printer?.printer_name || '', 'config-input-md') +
            toggle('printer', 'auto_print', 'Auto Print', 'Automatically print after each session without asking', c.printer?.auto_print) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Max Pages</div>
                    <div class="config-field-desc">Limit total prints per event. 0 = unlimited.</div>
                </div>
                <div class="config-field-control">
                    <input type="number" class="config-input config-input-sm" value="${c.printer?.max_pages || 0}" min="0"
                           onchange="admin.patchConfigField('printer', 'max_pages', Number(this.value))" />
                </div>
            </div>` +
            numberInput('printer', 'copies', 'Copies per Print', 'Number of copies each time a photo is printed', c.printer?.copies || 1)
        );

        // 9. GPIO / Hardware
        const gpioHtml = sectionCard('GPIO / Hardware',
            'Physical button and LED pin assignments for Raspberry Pi. Only relevant when running on Pi hardware.',
            numberInput('controls', 'capture_button_pin', 'Capture Button Pin', 'GPIO pin for the main capture button', c.controls?.capture_button_pin || 11) +
            numberInput('controls', 'print_button_pin', 'Print Button Pin', 'GPIO pin for the print button', c.controls?.print_button_pin || 7) +
            numberInput('controls', 'capture_led_pin', 'Capture LED Pin', 'GPIO pin for the capture indicator LED', c.controls?.capture_led_pin || 15) +
            numberInput('controls', 'print_led_pin', 'Print LED Pin', 'GPIO pin for the print indicator LED', c.controls?.print_led_pin || 13) +
            slider('controls', 'debounce_ms', 'Debounce', 'Milliseconds to debounce button presses', c.controls?.debounce_ms || 300, 50, 1000, 50, 'ms')
        );

        // 10. Chromakey
        const chromakeyHtml = sectionCard('Green Screen',
            'Chroma key settings for green screen backgrounds.',
            toggle('chromakey', 'enabled', 'Enable Chroma Key', 'Remove green background and replace with custom images', c.chromakey?.enabled) +
            slider('chromakey', 'hue_center', 'Hue Center', 'Center of the hue range to key out (120 = green)', c.chromakey?.hue_center || 120, 0, 180, 1, '') +
            slider('chromakey', 'hue_range', 'Hue Range', 'Width of the hue range around center', c.chromakey?.hue_range || 40, 5, 90, 1, '') +
            '<div class="config-row"><label class="config-label">Available Backgrounds</label>' +
            '<div id="admin-bg-list" class="admin-bg-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:0.5rem;margin-top:0.5rem;"></div></div>'
        );

        // 11. Email
        const emailHtml = sectionCard('Email',
            'Send photos directly to guests via email after their session.',
            toggle('email', 'enabled', 'Enable Email Sharing', 'Show an email option on the share screen', c.email?.enabled) +
            textInput('email', 'smtp_host', 'SMTP Host', 'Mail server hostname', c.email?.smtp_host || '', 'config-input-md') +
            numberInput('email', 'smtp_port', 'SMTP Port', 'Usually 587 for TLS', c.email?.smtp_port || 587) +
            textInput('email', 'smtp_user', 'SMTP Username', '', c.email?.smtp_user || '', 'config-input-md') +
            textInput('email', 'from_address', 'From Address', 'Sender email address', c.email?.from_address || '', 'config-input-md') +
            textInput('email', 'from_name', 'From Name', 'Sender display name', c.email?.from_name || 'Photo Booth', 'config-input-md') +
            textInput('email', 'subject', 'Subject Line', 'Email subject for photo deliveries', c.email?.subject || '', 'config-input-md')
        );

        // 12. Cloud Gallery
        const cloudGalleryHtml = sectionCard('Cloud Gallery',
            'Upload photos to a cloud gallery for permanent, stable share URLs. Works with gallery.cush.rocks or self-hosted hexi-photo-gallery.',
            toggle('cloud_gallery', 'enabled', 'Enable Cloud Gallery', 'Automatically upload photos to the cloud gallery', c.cloud_gallery?.enabled) +
            textInput('cloud_gallery', 'api_url', 'API URL', 'Gallery API endpoint, e.g. https://gallery.cush.rocks/api/v1', c.cloud_gallery?.api_url || '', 'config-input-md') +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">API Key</div>
                    <div class="config-field-desc">X-API-Key header value for authentication</div>
                </div>
                <div class="config-field-control">
                    <input type="password" class="config-input config-input-md" value="${this.escAttr(c.cloud_gallery?.api_key || '')}"
                           data-section="cloud_gallery" data-key="api_key"
                           onchange="admin.patchConfigField('cloud_gallery', 'api_key', this.value)" />
                </div>
            </div>` +
            textInput('cloud_gallery', 'gallery_id', 'Gallery ID', 'ID of the gallery to upload photos to', c.cloud_gallery?.gallery_id || '', 'config-input-md') +
            toggle('cloud_gallery', 'auto_upload', 'Auto Upload', 'Upload every photo automatically after capture', c.cloud_gallery?.auto_upload !== false) +
            `<div class="config-field">
                <div class="config-field-info">
                    <div class="config-field-label">Connection Status</div>
                    <div class="config-field-desc">Test the cloud gallery connection</div>
                </div>
                <div class="config-field-control">
                    <button type="button" class="btn btn-sm" id="cloud-gallery-test-btn"
                            onclick="admin.testCloudGallery()"
                            style="background:#f5f5ff; color:#6c63ff; border:1px solid #d0d0e8;">
                        Test Connection
                    </button>
                    <span id="cloud-gallery-status" style="margin-left:0.75rem; font-size:0.85rem;"></span>
                </div>
            </div>`
        );

        // 13. Advanced
        const advancedHtml = sectionCard('Advanced',
            'Server, plugin, and debug settings. Most users will not need to change these.',
            toggle('general', 'debug', 'Debug Mode', 'Enable verbose logging for troubleshooting', c.general?.debug) +
            numberInput('general', 'autostart_delay', 'Autostart Delay', 'Seconds to wait before booth starts on boot', c.general?.autostart_delay || 3) +
            textInput('general', 'save_dir', 'Save Directory', 'Where photos are stored on disk', c.general?.save_dir || 'data', 'config-input-md') +
            textInput('server', 'host', 'Server Host', 'Bind address (0.0.0.0 for all interfaces)', c.server?.host || '0.0.0.0', 'config-input-md') +
            numberInput('server', 'port', 'Server Port', 'HTTP port for the web interface', c.server?.port || 8000)
        );

        container.innerHTML = `<div class="config-form">
            ${eventSetupHtml}
            ${cameraHtml}
            ${photoSettingsHtml}
            ${sharingHtml}
            ${soundHtml}
            ${displayHtml}
            ${networkHtml}
            ${printingHtml}
            ${gpioHtml}
            ${chromakeyHtml}
            ${emailHtml}
            ${cloudGalleryHtml}
            ${advancedHtml}
        </div>`;

        // Load logo preview into config tab
        this.loadConfigLogoPreview();
        // Load backgrounds list for chromakey section
        this.loadBackgroundsList();
    }

    async loadBackgroundsList() {
        try {
            const res = await fetch('/api/admin/backgrounds');
            const data = await res.json();
            const container = document.getElementById('admin-bg-list');
            if (!container) return;
            const bgs = data.backgrounds || [];
            if (bgs.length === 0) {
                container.innerHTML = '<span style="color:var(--admin-text-muted);font-size:0.85rem;">No backgrounds found. Run bin/generate-backgrounds to create them.</span>';
                return;
            }
            container.innerHTML = bgs.map(bg => {
                const name = bg.replace(/\.[^.]+$/, '').replace(/-/g, ' ');
                return `<div style="text-align:center;">
                    <img src="/static/backgrounds/${bg}" alt="${name}" style="width:100%;height:60px;object-fit:cover;border-radius:4px;border:1px solid rgba(255,255,255,0.1);">
                    <div style="font-size:0.7rem;color:var(--admin-text-muted);margin-top:2px;text-transform:capitalize;">${name}</div>
                </div>`;
            }).join('');
        } catch (e) { /* ignore */ }
    }

    async loadConfigLogoPreview() {
        try {
            const res = await fetch('/api/admin/branding');
            const data = await res.json();
            const thumb = document.getElementById('cfg-logo-thumb');
            if (thumb && data.logo_url) {
                thumb.innerHTML = `<img src="${data.logo_url}?${Date.now()}" alt="Logo" />`;
            }
        } catch (e) { /* ignore */ }
    }

    escAttr(val) {
        return String(val).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Auto-save: patch a single config field immediately
    async patchConfigField(section, key, value) {
        const payload = {};
        payload[section] = {};
        payload[section][key] = value;

        try {
            const res = await fetch('/api/admin/config', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (res.ok) {
                // Update local config cache
                if (this.config && this.config[section]) {
                    this.config[section][key] = value;
                }
                this.showNotification('Saved', 'success');
            } else {
                const err = await res.json();
                this.showNotification(`Save failed: ${err.detail || 'Unknown error'}`, 'error');
            }
        } catch (e) {
            this.showNotification(`Save failed: ${e.message}`, 'error');
        }
    }

    // Debounced version for sliders
    patchConfigFieldDebounced(section, key, value) {
        clearTimeout(this._patchDebounce);
        this._patchDebounce = setTimeout(() => {
            this.patchConfigField(section, key, value);
        }, 400);
    }

    // Pose prompt management
    async updatePosePrompt(index, value) {
        const prompts = [...(this.config?.picture?.pose_prompts || [])];
        prompts[index] = value;
        await this.patchConfigField('picture', 'pose_prompts', prompts);
        // Don't re-render; the input is already updated
    }

    async removePosePrompt(index) {
        const prompts = [...(this.config?.picture?.pose_prompts || [])];
        prompts.splice(index, 1);
        await this.patchConfigField('picture', 'pose_prompts', prompts);
        this.renderConfigForm(this.config);
    }

    async addPosePrompt() {
        const prompts = [...(this.config?.picture?.pose_prompts || [])];
        prompts.push('New prompt!');
        await this.patchConfigField('picture', 'pose_prompts', prompts);
        this.renderConfigForm(this.config);
    }

    /* ── Gallery Tab ─────────────────────────────────────────────── */

    async loadGallery() {
        const container = document.getElementById('gallery-content');
        container.innerHTML = '<div class="loading">Loading gallery...</div>';

        // Fetch connection info for share URLs
        try {
            const connRes = await fetch('/api/admin/connection');
            const connInfo = await connRes.json();
            this._shareBaseUrl = `http://${connInfo.ip}:${connInfo.port}`;
        } catch (e) {
            this._shareBaseUrl = window.location.origin;
        }

        try {
            const res = await fetch('/api/gallery/?limit=100');
            const data = await res.json();
            this.renderGalleryGrid(data.photos);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load gallery: ${e.message}</div>`;
        }
    }

    renderGalleryGrid(photos) {
        const container = document.getElementById('gallery-content');

        if (!photos || photos.length === 0) {
            container.innerHTML = `<div class="empty-state">
                <div class="empty-icon">&#128247;</div>
                <h3>No photos yet</h3>
                <p>Photos will appear here after guests start using the booth.</p>
            </div>`;
            return;
        }

        const baseUrl = this._shareBaseUrl || window.location.origin;

        // Responsive column count based on container width
        const containerWidth = container.offsetWidth || 800;
        const columns = containerWidth > 900 ? 4 : containerWidth > 600 ? 3 : 2;

        // Distribute photos to columns (shortest-column-first for masonry)
        const columnPhotos = Array.from({ length: columns }, () => []);
        const columnHeights = new Array(columns).fill(0);
        for (const photo of photos) {
            const shortest = columnHeights.indexOf(Math.min(...columnHeights));
            columnPhotos[shortest].push(photo);
            columnHeights[shortest] += 1;
        }

        let html = '<div class="masonry-grid">';
        for (let c = 0; c < columns; c++) {
            html += '<div class="masonry-column">';
            for (const photo of columnPhotos[c]) {
                const date = new Date(photo.created_at).toLocaleString();
                const shareUrl = photo.share_token
                    ? `${baseUrl}/share/${photo.share_token}`
                    : null;
                html += `
                    <div class="gallery-card" data-photo-id="${photo.id}" data-photo-url="/api/gallery/${photo.id}">
                        <img data-src="${photo.photo_path && photo.photo_path.endsWith('.gif') ? '/api/gallery/' + photo.id : '/api/gallery/' + photo.id + '/thumbnail'}" alt="Photo" />
                        <div class="gallery-overlay">
                            <div class="gallery-date">${date}</div>
                            <div class="gallery-actions">
                                ${photo.share_token ? `<a href="/share/${photo.share_token}" target="_blank" class="btn btn-sm" onclick="event.stopPropagation()">Share</a>` : ''}
                                <button class="btn btn-sm btn-copy-link" data-copy-url="${shareUrl || ''}" data-photo-id="${photo.id}" onclick="event.stopPropagation()">${shareUrl ? 'Copy Link' : 'Get Link'}</button>
                                <button class="btn btn-sm btn-danger" data-delete-photo="${photo.id}" onclick="event.stopPropagation()">Delete</button>
                            </div>
                        </div>
                    </div>
                `;
            }
            html += '</div>';
        }
        html += '</div>';

        container.innerHTML = html;

        // Lazy load images with IntersectionObserver
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.onload = () => img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        }, { rootMargin: '200px' });

        container.querySelectorAll('.gallery-card img[data-src]').forEach(img => {
            observer.observe(img);
        });

        // Click card to open lightbox
        container.querySelectorAll('.gallery-card').forEach(card => {
            card.addEventListener('click', () => {
                this.showAdminLightbox(card.dataset.photoUrl, card.dataset.photoId);
            });
        });

        // Bind copy link buttons
        container.querySelectorAll('.btn-copy-link').forEach(btn => {
            btn.addEventListener('click', async () => {
                let url = btn.dataset.copyUrl;

                // If no share token, create one first
                if (!url) {
                    const photoId = btn.dataset.photoId;
                    try {
                        btn.textContent = 'Creating...';
                        const res = await fetch(`/api/gallery/${photoId}/share-token`, { method: 'POST' });
                        const data = await res.json();
                        if (data.share_token) {
                            url = `${baseUrl}/share/${data.share_token}`;
                            btn.dataset.copyUrl = url;
                        }
                    } catch (e) {
                        btn.textContent = 'Failed';
                        setTimeout(() => { btn.textContent = 'Get Link'; }, 2000);
                        return;
                    }
                }

                if (!url) return;

                // Get the freshest base URL before copying
                try {
                    const freshConn = await fetch('/api/admin/connection').then(r => r.json());
                    const freshBase = `http://${freshConn.ip}:${freshConn.port}`;
                    const token = url.split('/share/')[1];
                    if (token) url = `${freshBase}/share/${token}`;
                } catch (e) {}

                try {
                    await navigator.clipboard.writeText(url);
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Copy Link'; }, 2000);
                } catch (e) {
                    // Fallback for non-HTTPS contexts
                    const input = document.createElement('input');
                    input.value = url;
                    document.body.appendChild(input);
                    input.select();
                    document.execCommand('copy');
                    document.body.removeChild(input);
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Copy Link'; }, 2000);
                }
            });
        });

        // Bind delete buttons via event delegation
        container.querySelectorAll('[data-delete-photo]').forEach(btn => {
            btn.addEventListener('click', () => this.deletePhoto(btn.dataset.deletePhoto));
        });
    }

    showAdminLightbox(url, photoId) {
        // Remove any existing lightbox
        const existing = document.querySelector('.admin-lightbox-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'admin-lightbox-overlay';
        overlay.innerHTML = `
            <div class="admin-lightbox-content">
                <img src="${url}" alt="Photo">
                <div class="admin-lightbox-actions">
                    <a href="${url}" download class="btn btn-download">Download</a>
                    <button class="btn btn-close-lb">Close</button>
                </div>
            </div>
        `;

        // Close on overlay background click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        // Close button
        overlay.querySelector('.btn-close-lb').addEventListener('click', () => overlay.remove());

        document.body.appendChild(overlay);
        // Trigger animation
        requestAnimationFrame(() => overlay.classList.add('active'));

        // Escape key
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    async deletePhoto(id) {
        if (!confirm('Delete this photo?')) return;
        try {
            await fetch(`/api/gallery/${id}`, { method: 'DELETE' });
            this.loadGallery();
            this.showNotification('Photo deleted', 'success');
        } catch (e) {
            this.showNotification(`Delete failed: ${e.message}`, 'error');
        }
    }

    /* ── Cloud Gallery ──────────────────────────────────────────── */

    async testCloudGallery() {
        const btn = document.getElementById('cloud-gallery-test-btn');
        const status = document.getElementById('cloud-gallery-status');
        if (!btn || !status) return;

        btn.disabled = true;
        btn.textContent = 'Testing...';
        status.textContent = '';
        status.style.color = '';

        try {
            const res = await fetch('/api/admin/cloud-gallery/test');
            const data = await res.json();
            if (data.connected) {
                status.textContent = `Connected: ${data.gallery_name || data.slug || 'OK'}`;
                status.style.color = '#22c55e';
            } else {
                status.textContent = data.error || 'Not connected';
                status.style.color = '#ef4444';
            }
        } catch (e) {
            status.textContent = `Error: ${e.message}`;
            status.style.color = '#ef4444';
        }

        btn.disabled = false;
        btn.textContent = 'Test Connection';
    }

    /* ── Theme Tab ───────────────────────────────────────────────── */

    async loadTheme() {
        const container = document.getElementById('theme-content');

        // Read current CSS variables from theme.css (via config endpoint is indirect,
        // so we parse the currently loaded stylesheet)
        const vars = this.getCurrentCSSVariables();

        let html = '';

        // Branding / Logo section (outside the theme form)
        html += `<div class="config-section">
            <h3>Event Logo</h3>
            <div style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;">
                <div id="logo-preview" style="width:160px;height:100px;background:#f0f0f0;border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    <img id="admin-logo-preview" src="" alt="" style="display:none;max-width:100%;max-height:100%;object-fit:contain;">
                    <span id="no-logo-text" style="color:#999;font-size:0.85rem;">No logo uploaded</span>
                </div>
                <div style="display:flex;flex-direction:column;gap:0.5rem;">
                    <label class="btn btn-primary" style="cursor:pointer;">
                        Upload Logo
                        <input type="file" id="logo-upload" accept="image/*" hidden>
                    </label>
                    <button class="btn btn-danger btn-sm" id="remove-logo" style="display:none;">Remove</button>
                    <p style="font-size:0.8rem;color:#888;margin:0;">Recommended: PNG with transparent background, at least 400px wide</p>
                </div>
            </div>
        </div>`;

        html += '<form id="theme-form" class="config-form">';
        html += '<div class="config-section"><h3>Colors</h3>';

        const colorVars = [
            { key: '--pb-bg-primary', label: 'Background Primary' },
            { key: '--pb-bg-secondary', label: 'Background Secondary' },
            { key: '--pb-bg-card', label: 'Card Background' },
            { key: '--pb-accent', label: 'Accent Color' },
            { key: '--pb-accent-hover', label: 'Accent Hover' },
            { key: '--pb-text-primary', label: 'Text Primary' },
            { key: '--pb-text-secondary', label: 'Text Secondary' },
            { key: '--pb-success', label: 'Success' },
            { key: '--pb-error', label: 'Error' },
            { key: '--pb-warning', label: 'Warning' },
        ];

        for (const v of colorVars) {
            const current = vars[v.key] || '#000000';
            // Normalize to hex for color picker
            const hex = this.colorToHex(current.trim());
            html += `<div class="field">
                <label>${v.label}</label>
                <div class="color-field">
                    <input type="color" data-var="${v.key}" value="${hex}"
                           onchange="this.nextElementSibling.value=this.value; admin.previewThemeVar('${v.key}', this.value)" />
                    <input type="text" value="${hex}" class="color-text"
                           onchange="this.previousElementSibling.value=this.value; admin.previewThemeVar('${v.key}', this.value)" />
                </div>
            </div>`;
        }

        html += '</div>';

        html += '<div class="config-section"><h3>Typography</h3>';
        const fontValue = vars['--pb-font-family'] || "'Segoe UI', system-ui, sans-serif";
        html += `<div class="field">
            <label>Font Family</label>
            <select id="theme-font" data-var="--pb-font-family" onchange="admin.previewThemeVar('--pb-font-family', this.value)">
                <option value="'Segoe UI', system-ui, -apple-system, sans-serif" ${fontValue.includes('Segoe') ? 'selected' : ''}>Segoe UI (Default)</option>
                <option value="'Inter', sans-serif" ${fontValue.includes('Inter') ? 'selected' : ''}>Inter</option>
                <option value="'Poppins', sans-serif" ${fontValue.includes('Poppins') ? 'selected' : ''}>Poppins</option>
                <option value="'Roboto', sans-serif" ${fontValue.includes('Roboto') ? 'selected' : ''}>Roboto</option>
                <option value="'Georgia', serif" ${fontValue.includes('Georgia') ? 'selected' : ''}>Georgia</option>
            </select>
        </div>`;
        html += '</div>';

        html += `<div class="config-section"><h3>Preview</h3>
            <div class="theme-preview" id="theme-preview">
                <div class="preview-card">
                    <h2>Photo Booth</h2>
                    <p>This is how your booth will look with the current theme.</p>
                    <button class="btn btn-primary">Take Photo</button>
                </div>
            </div>
        </div>`;

        html += '<div class="form-actions"><button type="submit" class="btn btn-primary">Save Theme</button></div>';
        html += '</form>';

        container.innerHTML = html;

        document.getElementById('theme-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveTheme();
        });

        // Logo upload handler
        document.getElementById('logo-upload')?.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const form = new FormData();
            form.append('file', file);
            try {
                const res = await fetch('/api/admin/branding/logo', { method: 'POST', body: form });
                const data = await res.json();
                if (data.url) {
                    this.loadBrandingPreview();
                    this.showNotification('Logo uploaded!', 'success');
                }
            } catch (err) {
                this.showNotification('Logo upload failed: ' + err.message, 'error');
            }
        });

        // Remove logo handler
        document.getElementById('remove-logo')?.addEventListener('click', async () => {
            try {
                await fetch('/api/admin/branding/logo', { method: 'DELETE' });
                this.loadBrandingPreview();
                this.showNotification('Logo removed', 'success');
            } catch (err) {
                this.showNotification('Failed to remove logo: ' + err.message, 'error');
            }
        });

        // Load current branding
        this.loadBrandingPreview();
    }

    async loadBrandingPreview() {
        try {
            const res = await fetch('/api/admin/branding');
            const data = await res.json();
            const img = document.getElementById('admin-logo-preview');
            const noText = document.getElementById('no-logo-text');
            const removeBtn = document.getElementById('remove-logo');
            if (data.logo_url && img) {
                img.src = data.logo_url + '?' + Date.now();
                img.style.display = 'block';
                if (noText) noText.style.display = 'none';
                if (removeBtn) removeBtn.style.display = '';
            } else {
                if (img) img.style.display = 'none';
                if (noText) noText.style.display = '';
                if (removeBtn) removeBtn.style.display = 'none';
            }
        } catch (e) {
            // Branding endpoint may not be available
        }
    }

    getCurrentCSSVariables() {
        const vars = {};
        const root = document.documentElement;
        const computed = getComputedStyle(root);
        const varNames = [
            '--pb-bg-primary', '--pb-bg-secondary', '--pb-bg-card',
            '--pb-accent', '--pb-accent-hover', '--pb-accent-glow',
            '--pb-text-primary', '--pb-text-secondary',
            '--pb-success', '--pb-error', '--pb-warning',
            '--pb-font-family', '--pb-font-display',
        ];
        for (const name of varNames) {
            vars[name] = computed.getPropertyValue(name).trim();
        }
        return vars;
    }

    colorToHex(color) {
        if (color.startsWith('#') && color.length === 7) return color;
        if (color.startsWith('#') && color.length === 4) {
            return '#' + color[1] + color[1] + color[2] + color[2] + color[3] + color[3];
        }
        // Try rgb()
        const match = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
        if (match) {
            const r = parseInt(match[1]).toString(16).padStart(2, '0');
            const g = parseInt(match[2]).toString(16).padStart(2, '0');
            const b = parseInt(match[3]).toString(16).padStart(2, '0');
            return `#${r}${g}${b}`;
        }
        return '#000000';
    }

    previewThemeVar(varName, value) {
        document.documentElement.style.setProperty(varName, value);
    }

    async saveTheme() {
        const form = document.getElementById('theme-form');
        const variables = {};

        form.querySelectorAll('input[type="color"][data-var]').forEach(input => {
            variables[input.dataset.var] = input.value;
        });

        form.querySelectorAll('select[data-var]').forEach(select => {
            variables[select.dataset.var] = select.value;
        });

        // Also include non-color CSS vars with current computed values
        const computed = getComputedStyle(document.documentElement);
        const extraVars = [
            '--pb-accent-glow', '--pb-font-display',
            '--pb-font-size-title', '--pb-font-size-subtitle',
            '--pb-font-size-body', '--pb-font-size-countdown',
            '--pb-border-radius', '--pb-border-radius-sm',
            '--pb-spacing', '--pb-transition', '--pb-shadow', '--pb-blur',
        ];
        for (const v of extraVars) {
            const val = computed.getPropertyValue(v).trim();
            if (val) variables[v] = val;
        }

        // If font was set, also set display font
        if (variables['--pb-font-family']) {
            variables['--pb-font-display'] = variables['--pb-font-family'];
        }

        try {
            const res = await fetch('/api/admin/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ variables }),
            });
            if (res.ok) {
                this.showNotification('Theme saved!', 'success');
            } else {
                this.showNotification('Failed to save theme', 'error');
            }
        } catch (e) {
            this.showNotification(`Save failed: ${e.message}`, 'error');
        }
    }

    /* ── Templates Tab ───────────────────────────────────────────── */

    async loadTemplates() {
        if (!this.templateEditor) {
            this.templateEditor = new TemplateEditor(this);
        }
        this.templateEditor.init();
    }

    /* ── Analytics Tab ───────────────────────────────────────────── */

    async loadAnalytics() {
        const container = document.getElementById('analytics-content');
        container.innerHTML = '<div class="loading">Loading analytics...</div>';

        try {
            const res = await fetch('/api/admin/analytics');
            const data = await res.json();
            this.renderAnalytics(data);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load analytics: ${e.message}</div>`;
        }
    }

    renderAnalytics(data) {
        const container = document.getElementById('analytics-content');
        const counters = data.counters || {};
        const uptimeSec = data.uptime_seconds || 0;
        const hours = Math.floor(uptimeSec / 3600);
        const mins = Math.floor((uptimeSec % 3600) / 60);
        const uptimeStr = `${hours}h ${mins}m`;

        // Build photos-per-hour chart
        const pph = data.photos_per_hour || {};
        const pphEntries = Object.entries(pph);
        const maxCount = pphEntries.length > 0 ? Math.max(...pphEntries.map(e => e[1])) : 1;

        let chartHtml = '';
        if (pphEntries.length === 0) {
            chartHtml = '<div class="empty-state">No photo data yet</div>';
        } else {
            // Show last 24 entries max
            const recent = pphEntries.slice(-24);
            chartHtml = '<div class="bar-chart">';
            for (const [hour, count] of recent) {
                const pct = Math.round((count / maxCount) * 100);
                const label = hour.length >= 13 ? hour.slice(11, 13) + ':00' : hour;
                chartHtml += `
                    <div class="bar-row">
                        <span class="bar-label">${label}</span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:${pct}%"></div>
                        </div>
                        <span class="bar-count">${count}</span>
                    </div>`;
            }
            chartHtml += '</div>';
        }

        container.innerHTML = `
            <div class="cards">
                <div class="card">
                    <h3>Counters</h3>
                    <div class="card-row">Total Photos: <strong>${data.total_photos}</strong></div>
                    <div class="card-row">Session Photos: <strong>${counters.session_taken || 0}</strong></div>
                    <div class="card-row">Total Printed: <strong>${counters.total_printed || 0}</strong></div>
                    <div class="card-row">Session Printed: <strong>${counters.session_printed || 0}</strong></div>
                </div>
                <div class="card">
                    <h3>Uptime</h3>
                    <div class="card-row">${uptimeStr}</div>
                </div>
                <div class="card card-wide">
                    <h3>Photos Per Hour</h3>
                    ${chartHtml}
                </div>
                <div class="card">
                    <h3>Backup</h3>
                    <div class="card-row">Download all photos, gallery DB, and counters.</div>
                    <div style="margin-top:0.75rem">
                        <a href="/api/admin/backup" class="btn btn-primary" download>Download Backup</a>
                    </div>
                </div>
            </div>
        `;
    }

    /* ── Events Tab ─────────────────────────────────────────────── */

    async loadEvents() {
        const container = document.getElementById('events-content');
        if (!container) return;
        container.innerHTML = '<div class="loading">Loading events...</div>';

        // Ensure config is loaded so we know the active gallery
        if (!this.config) {
            try {
                const cfgRes = await fetch('/api/admin/config');
                this.config = await cfgRes.json();
            } catch (_) { /* ignore */ }
        }

        try {
            const res = await fetch('/api/admin/events');
            const data = await res.json();

            this.renderEvents(data.events, container, data.cloud_configured);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load events</div>`;
        }
    }

    renderEvents(events, container, cloudConfigured) {
        let html = `
            <div class="events-header">
                <h3>Events</h3>
                <button class="btn btn-primary" id="create-event-btn">+ New Event</button>
            </div>
            <p class="section-desc">Each event is a local album. Photos are tagged to the active event.${cloudConfigured ? ' Cloud-synced events also upload to gallery.cush.rocks.' : ''}</p>
        `;

        if (events.length === 0) {
            html += '<div class="empty-state"><p>No events yet. Create one to get started.</p></div>';
        } else {
            html += '<div class="events-list">';
            for (const event of events) {
                const isActive = !!event.is_active;
                const photoCount = event.photo_count || 0;
                const date = new Date(event.created_at).toLocaleDateString();
                const hasCloud = !!event.cloud_gallery_id;
                const publicUrl = hasCloud
                    ? `https://gallery.cush.rocks/${event.slug}`
                    : `${window.location.origin}/gallery?album=${event.id}`;
                const urlLabel = hasCloud ? publicUrl : 'Local Gallery';

                html += `
                    <div class="event-card ${isActive ? 'active' : ''}">
                        <div class="event-info">
                            <div class="event-name">${event.name} ${isActive ? '<span class="event-badge">Active</span>' : ''}${hasCloud ? '<span class="event-badge" style="background:#4caf50">Cloud</span>' : ''}</div>
                            <div class="event-meta">${photoCount} photos &middot; Created ${date}</div>
                            <div class="event-url"><a href="${publicUrl}" target="_blank">${urlLabel}</a></div>
                        </div>
                        <div class="event-actions">
                            ${!isActive ? `<button class="btn btn-sm btn-primary" data-activate-event="${event.id}">Activate</button>` : ''}
                            <button class="btn btn-sm" data-copy-event-url="${publicUrl}">Copy Link</button>
                            <button class="btn btn-sm btn-danger" data-delete-event="${event.id}">Delete</button>
                        </div>
                    </div>
                `;
            }
            html += '</div>';
        }

        container.innerHTML = html;

        // Bind create button
        document.getElementById('create-event-btn')?.addEventListener('click', () => this.showCreateEventDialog());

        // Bind activate buttons
        container.querySelectorAll('[data-activate-event]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.activateEvent;
                await fetch(`/api/admin/events/${id}/activate`, { method: 'POST' });
                this.showNotification('Event activated!', 'success');
                this.loadEvents();
                this.loadConfig();
            });
        });

        // Bind copy URL buttons
        container.querySelectorAll('[data-copy-event-url]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const url = btn.dataset.copyEventUrl;
                try {
                    await navigator.clipboard.writeText(url);
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Copy Link'; }, 2000);
                } catch (_) { /* ignore */ }
            });
        });

        // Bind delete buttons
        container.querySelectorAll('[data-delete-event]').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Delete this event and all its photos?')) return;
                await fetch(`/api/admin/events/${btn.dataset.deleteEvent}`, { method: 'DELETE' });
                this.showNotification('Event deleted', 'success');
                this.loadEvents();
            });
        });
    }

    showCreateEventDialog() {
        const name = prompt('Event name:');
        if (!name) return;

        const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
        this.createEvent(name, slug);
    }

    async createEvent(name, slug) {
        try {
            const res = await fetch('/api/admin/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, slug }),
            });
            if (res.ok) {
                this.showNotification('Event created!', 'success');
                this.loadEvents();
                this.loadConfig();
            } else {
                this.showNotification('Failed to create event', 'error');
            }
        } catch (e) {
            this.showNotification('Error: ' + e.message, 'error');
        }
    }

    /* ── Utilities ───────────────────────────────────────────────── */

    formatLabel(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    showNotification(message, type = 'info') {
        const existing = document.querySelector('.notification');
        if (existing) existing.remove();

        const el = document.createElement('div');
        el.className = `notification notification-${type}`;
        el.textContent = message;
        document.body.appendChild(el);

        setTimeout(() => el.classList.add('show'), 10);
        setTimeout(() => {
            el.classList.remove('show');
            setTimeout(() => el.remove(), 300);
        }, 3000);
    }
}

/* ── Template Editor ─────────────────────────────────────────────── */

class TemplateEditor {
    constructor(adminPanel) {
        this.admin = adminPanel;
        this.currentTemplate = null;
        this.currentName = null;
        this.slots = [];
        this.selectedSlot = null;
        this.footer = null;
        this.textOverlays = [];
        this.imageOverlays = [];
        this.selectedTextOverlay = null;
        this.isDragging = false;
        this.isResizing = false;
        this.dragOffset = { x: 0, y: 0 };
    }

    async init() {
        await this.loadTemplateList();
        this.bindSidebarButtons();
    }

    bindSidebarButtons() {
        const newBtn = document.getElementById('new-template-btn');
        if (newBtn && !newBtn._bound) {
            newBtn._bound = true;
            newBtn.addEventListener('click', () => this.createNew());
        }
    }

    async loadTemplateList() {
        try {
            const res = await fetch('/api/admin/templates');
            const data = await res.json();
            const list = document.getElementById('template-list');
            if (!list) return;
            list.innerHTML = data.templates.map(name => `
                <div class="tpl-item ${name === this.currentName ? 'active' : ''}"
                     data-name="${name}">
                    <span>${name}</span>
                    <button class="btn-icon-small delete-tpl" data-name="${name}">&times;</button>
                </div>
            `).join('');

            list.querySelectorAll('.tpl-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if (e.target.classList.contains('delete-tpl')) return;
                    this.loadTemplate(item.dataset.name);
                });
            });

            list.querySelectorAll('.delete-tpl').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteTemplate(btn.dataset.name);
                });
            });

            // Auto-load first template if none selected
            if (!this.currentName && data.templates.length > 0) {
                this.loadTemplate(data.templates[0]);
            }
        } catch (e) {
            this.admin.showNotification('Failed to load template list: ' + e.message, 'error');
        }
    }

    async loadTemplate(name) {
        try {
            const res = await fetch(`/api/admin/templates/${name}`);
            if (!res.ok) throw new Error('Template not found');
            const data = await res.json();
            this.currentTemplate = data;
            this.currentName = name;
            this.slots = (data.slots || []).map(s => ({...s}));
            this.footer = data.footer ? {...data.footer} : null;
            this.textOverlays = (data.text_overlays || []).map(t => ({...t}));
            this.imageOverlays = (data.image_overlays || []).map(i => ({...i}));
            this.selectedTextOverlay = null;
            this.renderEditorUI();
            this.loadTemplateList();
        } catch (e) {
            this.admin.showNotification('Failed to load template: ' + e.message, 'error');
        }
    }

    createNew() {
        this.currentName = null;
        this.currentTemplate = {
            name: 'custom',
            width_inches: 4,
            height_inches: 6,
            dpi: 600,
            background: '#ffffff',
        };
        this.slots = [
            { x: 0.05, y: 0.05, width: 0.9, height: 0.4, rotation: 0 }
        ];
        this.footer = null;
        this.textOverlays = [];
        this.imageOverlays = [];
        this.selectedSlot = null;
        this.selectedTextOverlay = null;
        this.renderEditorUI();
    }

    renderEditorUI() {
        const area = document.getElementById('template-editor-area');
        if (!area) return;

        const tpl = this.currentTemplate;
        const dpiOptions = [300, 600].map(d =>
            `<option value="${d}" ${tpl.dpi === d ? 'selected' : ''}>${d}</option>`
        ).join('');

        area.innerHTML = `
            <div class="template-toolbar">
                <div class="template-name-edit">
                    <input type="text" id="template-name" placeholder="Template name"
                           value="${this.currentName || tpl.name || ''}">
                </div>
                <div class="template-size-controls">
                    <label>Width (in):</label>
                    <input type="number" id="tpl-width" value="${tpl.width_inches}" step="0.5" min="1" max="12" class="input-small">
                    <label>Height (in):</label>
                    <input type="number" id="tpl-height" value="${tpl.height_inches}" step="0.5" min="1" max="12" class="input-small">
                    <label>DPI:</label>
                    <select id="tpl-dpi" class="input-small">${dpiOptions}</select>
                </div>
                <div class="template-actions">
                    <button class="btn-secondary" id="add-slot-btn">+ Add Photo Slot</button>
                    <button class="btn-secondary" id="add-text-btn">+ Add Text</button>
                    <button class="btn-secondary" id="toggle-footer-btn">${this.footer ? 'Remove Footer' : 'Add Footer'}</button>
                    <button class="btn btn-primary" id="save-template-btn">Save</button>
                </div>
            </div>
            <div class="template-canvas-wrapper">
                <div class="template-canvas" id="template-canvas"></div>
            </div>
            <div class="slot-properties" id="slot-properties" style="display:none">
                <h4>Slot Properties</h4>
                <label>X: <input type="range" id="slot-x" min="0" max="100" step="1"> <span id="slot-x-val"></span>%</label>
                <label>Y: <input type="range" id="slot-y" min="0" max="100" step="1"> <span id="slot-y-val"></span>%</label>
                <label>Width: <input type="range" id="slot-w" min="5" max="100" step="1"> <span id="slot-w-val"></span>%</label>
                <label>Height: <input type="range" id="slot-h" min="5" max="100" step="1"> <span id="slot-h-val"></span>%</label>
                <label>Rotation: <input type="range" id="slot-rot" min="-45" max="45" step="1" value="0"> <span id="slot-rot-val">0</span>&deg;</label>
                <button class="btn-text" id="delete-slot-btn" style="color:#f44336">Delete Slot</button>
            </div>
            <div class="footer-properties" id="footer-properties" style="display:none">
                <h4>Footer</h4>
                <label>Text: <input type="text" id="footer-text" class="input-field" placeholder="{event_name} - {date}"></label>
                <label>Font Size: <input type="number" id="footer-font-size" value="18" min="8" max="48" class="input-small"></label>
                <label>Color: <input type="color" id="footer-color" value="#333333"></label>
                <label>Y Position: <input type="range" id="footer-y" min="70" max="99" step="1"> <span id="footer-y-val"></span>%</label>
            </div>
            <div class="text-overlay-properties" id="text-overlay-properties" style="display:none">
                <h4>Text Overlay</h4>
                <label>Text: <input type="text" id="tov-text" class="input-field" placeholder="{event_name}"></label>
                <label>X: <input type="range" id="tov-x" min="0" max="100" step="1"> <span id="tov-x-val"></span>%</label>
                <label>Y: <input type="range" id="tov-y" min="0" max="100" step="1"> <span id="tov-y-val"></span>%</label>
                <label>Font Size: <input type="number" id="tov-font-size" value="18" min="6" max="72" class="input-small"></label>
                <label>Color: <input type="color" id="tov-color" value="#ffffff"></label>
                <label>Align: <select id="tov-align" class="input-small">
                    <option value="left">Left</option>
                    <option value="center" selected>Center</option>
                    <option value="right">Right</option>
                </select></label>
                <label>Rotation: <input type="range" id="tov-rot" min="-180" max="180" step="1" value="0"> <span id="tov-rot-val">0</span>&deg;</label>
                <label>Opacity: <input type="range" id="tov-opacity" min="0" max="100" step="1" value="100"> <span id="tov-opacity-val">100</span>%</label>
                <button class="btn-text" id="delete-text-overlay-btn" style="color:#f44336">Delete Text Overlay</button>
            </div>
        `;

        // Bind size change to re-render canvas
        ['tpl-width', 'tpl-height'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => this.renderCanvas());
        });

        // Bind buttons
        document.getElementById('add-slot-btn')?.addEventListener('click', () => this.addSlot());
        document.getElementById('add-text-btn')?.addEventListener('click', () => this.addTextOverlay());
        document.getElementById('toggle-footer-btn')?.addEventListener('click', () => this.toggleFooter());
        document.getElementById('save-template-btn')?.addEventListener('click', () => this.save());
        document.getElementById('delete-text-overlay-btn')?.addEventListener('click', () => {
            if (this.selectedTextOverlay !== null) this.deleteTextOverlay(this.selectedTextOverlay);
        });
        document.getElementById('delete-slot-btn')?.addEventListener('click', () => {
            if (this.selectedSlot !== null) this.deleteSlot(this.selectedSlot);
        });

        // Bind slot property sliders
        ['slot-x', 'slot-y', 'slot-w', 'slot-h', 'slot-rot'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => this.onSliderChange());
            }
        });

        // Bind footer property inputs
        ['footer-text', 'footer-font-size', 'footer-color', 'footer-y'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => this.onFooterInputChange());
            }
        });

        // Bind text overlay property inputs
        ['tov-text', 'tov-x', 'tov-y', 'tov-font-size', 'tov-color', 'tov-align', 'tov-rot', 'tov-opacity'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => this.onTextOverlayInputChange());
            }
        });

        this.renderCanvas();
        this.updateFooterPanel();
    }

    renderCanvas() {
        const canvas = document.getElementById('template-canvas');
        if (!canvas) return;

        const w = parseFloat(document.getElementById('tpl-width')?.value || this.currentTemplate.width_inches);
        const h = parseFloat(document.getElementById('tpl-height')?.value || this.currentTemplate.height_inches);
        const maxHeight = 500;
        const scale = maxHeight / h;
        canvas.style.width = `${w * scale}px`;
        canvas.style.height = `${maxHeight}px`;
        canvas.style.background = this.currentTemplate.background || '#ffffff';

        canvas.innerHTML = '';

        // Render slots
        this.slots.forEach((slot, i) => {
            const el = document.createElement('div');
            el.className = 'canvas-slot' + (this.selectedSlot === i ? ' selected' : '');
            el.dataset.index = i;
            el.style.left = `${slot.x * 100}%`;
            el.style.top = `${slot.y * 100}%`;
            el.style.width = `${slot.width * 100}%`;
            el.style.height = `${slot.height * 100}%`;
            if (slot.rotation) el.style.transform = `rotate(${slot.rotation}deg)`;
            el.innerHTML = `<span class="slot-label">${i + 1}</span>`;

            // Drag to move
            el.addEventListener('mousedown', (e) => this.startDrag(e, i));
            el.addEventListener('touchstart', (e) => this.startDrag(e, i), {passive: false});

            // Resize handle
            const handle = document.createElement('div');
            handle.className = 'resize-handle';
            handle.addEventListener('mousedown', (e) => { e.stopPropagation(); this.startResize(e, i); });
            handle.addEventListener('touchstart', (e) => { e.stopPropagation(); this.startResize(e, i); }, {passive: false});
            el.appendChild(handle);

            // Click to select
            el.addEventListener('click', (e) => { e.stopPropagation(); this.selectSlot(i); });

            canvas.appendChild(el);
        });

        // Render footer
        if (this.footer) {
            const footerEl = document.createElement('div');
            footerEl.className = 'canvas-footer';
            footerEl.style.top = `${(this.footer.y || 0.95) * 100}%`;
            footerEl.style.height = `${(this.footer.height || 0.04) * 100}%`;
            footerEl.textContent = this.footer.text || 'Footer text';
            footerEl.style.fontSize = `${(this.footer.font_size || 18) * 0.5}px`;
            footerEl.style.color = this.footer.color || '#333';
            canvas.appendChild(footerEl);
        }

        // Render text overlays
        this.textOverlays.forEach((tov, i) => {
            const el = document.createElement('div');
            el.className = 'canvas-text-overlay' + (this.selectedTextOverlay === i ? ' selected' : '');
            el.dataset.textIndex = i;
            el.style.left = `${tov.x * 100}%`;
            el.style.top = `${tov.y * 100}%`;
            el.style.color = tov.color || '#ffffff';
            el.style.fontSize = `${(tov.font_size || 18) * 0.6}px`;
            el.style.opacity = tov.opacity !== undefined ? tov.opacity : 1;
            el.style.textAlign = tov.align || 'center';
            if (tov.rotation) el.style.transform = `rotate(${tov.rotation}deg)`;
            if (tov.align === 'center') el.style.transform = (el.style.transform || '') + ' translateX(-50%)';
            else if (tov.align === 'right') el.style.transform = (el.style.transform || '') + ' translateX(-100%)';
            el.textContent = tov.text || 'Text';
            el.style.position = 'absolute';
            el.style.cursor = 'move';
            el.style.whiteSpace = 'nowrap';
            el.style.userSelect = 'none';
            el.style.zIndex = '10';
            if (this.selectedTextOverlay === i) {
                el.style.outline = '2px dashed #00bcd4';
                el.style.outlineOffset = '2px';
            }

            el.addEventListener('mousedown', (e) => this.startTextDrag(e, i));
            el.addEventListener('touchstart', (e) => this.startTextDrag(e, i), {passive: false});
            el.addEventListener('click', (e) => { e.stopPropagation(); this.selectTextOverlay(i); });

            canvas.appendChild(el);
        });

        // Clicking canvas background deselects
        canvas.addEventListener('click', (e) => {
            if (e.target === canvas) this.deselectAll();
        });
    }

    startDrag(e, index) {
        e.preventDefault();
        this.isDragging = true;
        this.selectedSlot = index;
        const canvas = document.getElementById('template-canvas');
        const rect = canvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        this.dragOffset = {
            x: (clientX - rect.left) / rect.width - this.slots[index].x,
            y: (clientY - rect.top) / rect.height - this.slots[index].y,
        };

        const onMove = (e) => {
            if (!this.isDragging) return;
            const cx = e.touches ? e.touches[0].clientX : e.clientX;
            const cy = e.touches ? e.touches[0].clientY : e.clientY;
            const newX = Math.max(0, Math.min(1 - this.slots[index].width,
                (cx - rect.left) / rect.width - this.dragOffset.x));
            const newY = Math.max(0, Math.min(1 - this.slots[index].height,
                (cy - rect.top) / rect.height - this.dragOffset.y));
            this.slots[index].x = Math.round(newX * 100) / 100;
            this.slots[index].y = Math.round(newY * 100) / 100;
            this.renderCanvas();
            this.updateSlotProperties();
        };

        const onUp = () => {
            this.isDragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        document.addEventListener('touchmove', onMove, {passive: false});
        document.addEventListener('touchend', onUp);

        this.selectSlot(index);
    }

    startResize(e, index) {
        e.preventDefault();
        this.isResizing = true;
        this.selectedSlot = index;
        const canvas = document.getElementById('template-canvas');
        const rect = canvas.getBoundingClientRect();

        const onMove = (e) => {
            if (!this.isResizing) return;
            const cx = e.touches ? e.touches[0].clientX : e.clientX;
            const cy = e.touches ? e.touches[0].clientY : e.clientY;
            const slot = this.slots[index];
            const newW = Math.max(0.05, Math.min(1 - slot.x,
                (cx - rect.left) / rect.width - slot.x));
            const newH = Math.max(0.05, Math.min(1 - slot.y,
                (cy - rect.top) / rect.height - slot.y));
            slot.width = Math.round(newW * 100) / 100;
            slot.height = Math.round(newH * 100) / 100;
            this.renderCanvas();
            this.updateSlotProperties();
        };

        const onUp = () => {
            this.isResizing = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        document.addEventListener('touchmove', onMove, {passive: false});
        document.addEventListener('touchend', onUp);

        this.selectSlot(index);
    }

    selectSlot(index) {
        this.selectedSlot = index;
        this.selectedTextOverlay = null;
        document.getElementById('text-overlay-properties').style.display = 'none';
        this.renderCanvas();
        this.updateSlotProperties();
        document.getElementById('slot-properties').style.display = 'block';
    }

    deselectAll() {
        this.selectedSlot = null;
        this.selectedTextOverlay = null;
        document.getElementById('slot-properties').style.display = 'none';
        document.getElementById('text-overlay-properties').style.display = 'none';
        this.renderCanvas();
    }

    updateSlotProperties() {
        if (this.selectedSlot === null) return;
        const slot = this.slots[this.selectedSlot];
        if (!slot) return;

        const setSlider = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val;
            const valEl = document.getElementById(id + '-val');
            if (valEl) valEl.textContent = val;
        };

        setSlider('slot-x', Math.round(slot.x * 100));
        setSlider('slot-y', Math.round(slot.y * 100));
        setSlider('slot-w', Math.round(slot.width * 100));
        setSlider('slot-h', Math.round(slot.height * 100));
        setSlider('slot-rot', slot.rotation || 0);
    }

    onSliderChange() {
        if (this.selectedSlot === null) return;
        const slot = this.slots[this.selectedSlot];

        const getVal = (id) => {
            const el = document.getElementById(id);
            const val = el ? parseFloat(el.value) : 0;
            const valEl = document.getElementById(id + '-val');
            if (valEl) valEl.textContent = Math.round(val);
            return val;
        };

        slot.x = getVal('slot-x') / 100;
        slot.y = getVal('slot-y') / 100;
        slot.width = getVal('slot-w') / 100;
        slot.height = getVal('slot-h') / 100;
        slot.rotation = getVal('slot-rot');

        this.renderCanvas();
    }

    addSlot() {
        this.slots.push({
            x: 0.1,
            y: 0.1 + this.slots.length * 0.22,
            width: 0.8,
            height: 0.2,
            rotation: 0
        });
        this.renderCanvas();
    }

    deleteSlot(index) {
        this.slots.splice(index, 1);
        this.selectedSlot = null;
        document.getElementById('slot-properties').style.display = 'none';
        this.renderCanvas();
    }

    addTextOverlay() {
        this.textOverlays.push({
            text: '{event_name}',
            x: 0.5,
            y: 0.85 + this.textOverlays.length * 0.05,
            font_size: 18,
            color: '#ffffff',
            align: 'center',
            rotation: 0,
            opacity: 1.0,
        });
        this.selectedTextOverlay = this.textOverlays.length - 1;
        this.renderCanvas();
        this.updateTextOverlayProperties();
    }

    deleteTextOverlay(index) {
        this.textOverlays.splice(index, 1);
        this.selectedTextOverlay = null;
        document.getElementById('text-overlay-properties').style.display = 'none';
        this.renderCanvas();
    }

    selectTextOverlay(index) {
        this.selectedTextOverlay = index;
        this.selectedSlot = null;
        document.getElementById('slot-properties').style.display = 'none';
        document.getElementById('text-overlay-properties').style.display = 'block';
        this.updateTextOverlayProperties();
        this.renderCanvas();
    }

    updateTextOverlayProperties() {
        if (this.selectedTextOverlay === null) return;
        const tov = this.textOverlays[this.selectedTextOverlay];
        if (!tov) return;

        const setText = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
        const setSlider = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val;
            const valEl = document.getElementById(id + '-val');
            if (valEl) valEl.textContent = Math.round(val);
        };

        setText('tov-text', tov.text || '');
        setSlider('tov-x', Math.round(tov.x * 100));
        setSlider('tov-y', Math.round(tov.y * 100));
        setText('tov-font-size', tov.font_size || 18);
        setText('tov-color', tov.color || '#ffffff');
        setText('tov-align', tov.align || 'center');
        setSlider('tov-rot', tov.rotation || 0);
        setSlider('tov-opacity', Math.round((tov.opacity !== undefined ? tov.opacity : 1) * 100));
    }

    onTextOverlayInputChange() {
        if (this.selectedTextOverlay === null) return;
        const tov = this.textOverlays[this.selectedTextOverlay];

        const getText = (id) => { const el = document.getElementById(id); return el ? el.value : ''; };
        const getNum = (id) => { const el = document.getElementById(id); return el ? parseFloat(el.value) : 0; };

        tov.text = getText('tov-text');
        tov.x = getNum('tov-x') / 100;
        tov.y = getNum('tov-y') / 100;
        tov.font_size = getNum('tov-font-size') || 18;
        tov.color = getText('tov-color') || '#ffffff';
        tov.align = getText('tov-align') || 'center';
        tov.rotation = getNum('tov-rot');
        tov.opacity = getNum('tov-opacity') / 100;

        // Update display values
        ['tov-x', 'tov-y', 'tov-rot', 'tov-opacity'].forEach(id => {
            const el = document.getElementById(id);
            const valEl = document.getElementById(id + '-val');
            if (el && valEl) valEl.textContent = Math.round(parseFloat(el.value));
        });

        this.renderCanvas();
    }

    startTextDrag(e, index) {
        e.preventDefault();
        this.isDragging = true;
        this.selectedTextOverlay = index;
        this.selectedSlot = null;
        const canvas = document.getElementById('template-canvas');
        const rect = canvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        const tov = this.textOverlays[index];
        this.dragOffset = {
            x: (clientX - rect.left) / rect.width - tov.x,
            y: (clientY - rect.top) / rect.height - tov.y,
        };

        const onMove = (e) => {
            if (!this.isDragging) return;
            const cx = e.touches ? e.touches[0].clientX : e.clientX;
            const cy = e.touches ? e.touches[0].clientY : e.clientY;
            tov.x = Math.max(0, Math.min(1, (cx - rect.left) / rect.width - this.dragOffset.x));
            tov.y = Math.max(0, Math.min(1, (cy - rect.top) / rect.height - this.dragOffset.y));
            tov.x = Math.round(tov.x * 100) / 100;
            tov.y = Math.round(tov.y * 100) / 100;
            this.renderCanvas();
            this.updateTextOverlayProperties();
        };

        const onUp = () => {
            this.isDragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        document.addEventListener('touchmove', onMove, {passive: false});
        document.addEventListener('touchend', onUp);

        this.selectTextOverlay(index);
    }

    toggleFooter() {
        if (this.footer) {
            this.footer = null;
        } else {
            this.footer = {
                y: 0.95,
                height: 0.04,
                text: '{event_name} - {date}',
                font_size: 18,
                color: '#333333'
            };
        }
        // Update button text
        const btn = document.getElementById('toggle-footer-btn');
        if (btn) btn.textContent = this.footer ? 'Remove Footer' : 'Add Footer';
        this.updateFooterPanel();
        this.renderCanvas();
    }

    updateFooterPanel() {
        const panel = document.getElementById('footer-properties');
        if (!panel) return;
        if (!this.footer) {
            panel.style.display = 'none';
            return;
        }
        panel.style.display = 'block';

        const setText = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
        setText('footer-text', this.footer.text || '');
        setText('footer-font-size', this.footer.font_size || 18);
        setText('footer-color', this.footer.color || '#333333');

        const ySlider = document.getElementById('footer-y');
        if (ySlider) ySlider.value = Math.round((this.footer.y || 0.95) * 100);
        const yVal = document.getElementById('footer-y-val');
        if (yVal) yVal.textContent = Math.round((this.footer.y || 0.95) * 100);
    }

    onFooterInputChange() {
        if (!this.footer) return;
        const getText = (id) => { const el = document.getElementById(id); return el ? el.value : ''; };
        const getNum = (id) => { const el = document.getElementById(id); return el ? parseFloat(el.value) : 0; };

        this.footer.text = getText('footer-text');
        this.footer.font_size = getNum('footer-font-size') || 18;
        this.footer.color = getText('footer-color') || '#333333';

        const yVal = getNum('footer-y');
        this.footer.y = yVal / 100;
        const yValEl = document.getElementById('footer-y-val');
        if (yValEl) yValEl.textContent = Math.round(yVal);

        this.renderCanvas();
    }

    async save() {
        const name = (document.getElementById('template-name')?.value || 'custom').trim();
        if (!name) {
            this.admin.showNotification('Template name is required', 'error');
            return;
        }

        // Sanitize name for filename
        const safeName = name.replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase();

        const template = {
            name: safeName,
            width_inches: parseFloat(document.getElementById('tpl-width')?.value || 4),
            height_inches: parseFloat(document.getElementById('tpl-height')?.value || 6),
            dpi: parseInt(document.getElementById('tpl-dpi')?.value || 600),
            background: this.currentTemplate?.background || '#ffffff',
            slots: this.slots.map(s => ({
                x: s.x,
                y: s.y,
                width: s.width,
                height: s.height,
                rotation: s.rotation || 0
            })),
        };
        if (this.footer) {
            template.footer = { ...this.footer };
        }
        if (this.textOverlays.length > 0) {
            template.text_overlays = this.textOverlays.map(t => ({...t}));
        }
        if (this.imageOverlays.length > 0) {
            template.image_overlays = this.imageOverlays.map(i => ({...i}));
        }

        try {
            const res = await fetch(`/api/admin/templates/${safeName}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(template),
            });
            if (res.ok) {
                this.currentName = safeName;
                this.admin.showNotification('Template saved!', 'success');
                this.loadTemplateList();
            } else {
                const err = await res.json();
                this.admin.showNotification('Save failed: ' + (err.detail || 'Unknown error'), 'error');
            }
        } catch (e) {
            this.admin.showNotification('Save failed: ' + e.message, 'error');
        }
    }

    async deleteTemplate(name) {
        if (!confirm(`Delete template "${name}"?`)) return;
        try {
            const res = await fetch(`/api/admin/templates/${name}`, { method: 'DELETE' });
            if (res.ok) {
                if (this.currentName === name) {
                    this.currentName = null;
                    this.currentTemplate = null;
                    const area = document.getElementById('template-editor-area');
                    if (area) {
                        area.innerHTML = '<div class="template-empty"><p>Select a template from the sidebar or create a new one.</p></div>';
                    }
                }
                this.admin.showNotification('Template deleted', 'success');
                this.loadTemplateList();
            } else {
                const err = await res.json();
                this.admin.showNotification('Delete failed: ' + (err.detail || 'Unknown error'), 'error');
            }
        } catch (e) {
            this.admin.showNotification('Delete failed: ' + e.message, 'error');
        }
    }
}

const admin = new AdminPanel();
document.addEventListener('DOMContentLoaded', () => admin.init());
