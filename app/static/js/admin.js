/* Admin Panel JavaScript */

class AdminPanel {
    constructor() {
        this.currentTab = 'system';
        this.config = null;
    }

    async init() {
        this.bindTabs();
        this.showTab('system');
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
        // When using zoom, reset manual crop to let zoom handle it
        await this.updateFraming({ zoom: zoom });
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

        // Reset zoom slider when manually adjusting crop
        const zoomSlider = document.getElementById('zoom-slider');
        if (zoomSlider) {
            zoomSlider.value = 1;
            document.getElementById('zoom-value').textContent = '1.0x';
        }

        await this.updateFraming({
            crop_x: cropX,
            crop_y: cropY,
            crop_width: cropW,
            crop_height: cropH,
            zoom: 1.0,
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
        const sections = Object.entries(config);

        let html = '<form id="config-form" class="config-form">';

        for (const [section, values] of sections) {
            html += `<div class="config-section"><h3>${this.formatLabel(section)}</h3>`;
            html += this.renderFields(section, values);
            html += '</div>';
        }

        html += '<div class="form-actions"><button type="submit" class="btn btn-primary">Save Configuration</button></div>';
        html += '</form>';

        container.innerHTML = html;

        document.getElementById('config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveConfig();
        });
    }

    renderFields(section, values, prefix = '') {
        let html = '';
        const path = prefix ? `${prefix}.` : `${section}.`;

        for (const [key, value] of Object.entries(values)) {
            const fieldName = `${path}${key}`;
            const label = this.formatLabel(key);

            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                html += `<div class="field-group"><h4>${label}</h4>`;
                html += this.renderFields(section, value, prefix ? `${prefix}.${key}` : `${section}.${key}`);
                html += '</div>';
                continue;
            }

            html += `<div class="field">`;
            html += `<label for="${fieldName}">${label}</label>`;

            if (typeof value === 'boolean') {
                html += `<label class="toggle">
                    <input type="checkbox" id="${fieldName}" data-path="${fieldName}" ${value ? 'checked' : ''} />
                    <span class="toggle-slider"></span>
                </label>`;
            } else if (typeof value === 'number') {
                html += `<input type="number" id="${fieldName}" data-path="${fieldName}" value="${value}" />`;
            } else if (Array.isArray(value)) {
                html += `<input type="text" id="${fieldName}" data-path="${fieldName}" value="${JSON.stringify(value)}" class="array-input" />`;
            } else {
                // Check if it's a color
                if (typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value)) {
                    html += `<div class="color-field">
                        <input type="color" id="${fieldName}-color" data-path="${fieldName}" value="${value}" />
                        <input type="text" id="${fieldName}" data-path="${fieldName}" value="${value}" class="color-text" />
                    </div>`;
                } else {
                    html += `<input type="text" id="${fieldName}" data-path="${fieldName}" value="${value}" />`;
                }
            }

            html += '</div>';
        }

        return html;
    }

    async saveConfig() {
        const form = document.getElementById('config-form');
        const data = this.formToObject(form);

        try {
            const res = await fetch('/api/admin/config', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (res.ok) {
                this.showNotification('Configuration saved!', 'success');
            } else {
                const err = await res.json();
                this.showNotification(`Save failed: ${err.detail || 'Unknown error'}`, 'error');
            }
        } catch (e) {
            this.showNotification(`Save failed: ${e.message}`, 'error');
        }
    }

    formToObject(form) {
        const result = {};
        const inputs = form.querySelectorAll('input[data-path]');

        inputs.forEach(input => {
            const path = input.dataset.path;
            // Skip duplicate color text inputs
            if (input.type === 'color') return;

            const parts = path.split('.');
            let obj = result;

            for (let i = 0; i < parts.length - 1; i++) {
                if (!obj[parts[i]]) obj[parts[i]] = {};
                obj = obj[parts[i]];
            }

            const key = parts[parts.length - 1];

            if (input.type === 'checkbox') {
                obj[key] = input.checked;
            } else if (input.type === 'number') {
                obj[key] = Number(input.value);
            } else if (input.classList.contains('array-input')) {
                try {
                    obj[key] = JSON.parse(input.value);
                } catch {
                    obj[key] = input.value;
                }
            } else {
                obj[key] = input.value;
            }
        });

        return result;
    }

    /* ── Gallery Tab ─────────────────────────────────────────────── */

    async loadGallery() {
        const container = document.getElementById('gallery-content');
        container.innerHTML = '<div class="loading">Loading gallery...</div>';

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

        let html = '<div class="gallery-grid">';
        for (const photo of photos) {
            const date = new Date(photo.created_at).toLocaleString();
            html += `
                <div class="gallery-item">
                    <img src="/api/gallery/${photo.id}" alt="Photo" loading="lazy" />
                    <div class="gallery-overlay">
                        <div class="gallery-date">${date}</div>
                        <div class="gallery-actions">
                            ${photo.share_token ? `<a href="/share/${photo.share_token}" target="_blank" class="btn btn-sm">Share</a>` : ''}
                            <button class="btn btn-sm btn-danger" onclick="admin.deletePhoto('${photo.id}')">Delete</button>
                        </div>
                    </div>
                </div>
            `;
        }
        html += '</div>';

        container.innerHTML = html;
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
        this.selectedSlot = null;
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
        `;

        // Bind size change to re-render canvas
        ['tpl-width', 'tpl-height'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => this.renderCanvas());
        });

        // Bind buttons
        document.getElementById('add-slot-btn')?.addEventListener('click', () => this.addSlot());
        document.getElementById('toggle-footer-btn')?.addEventListener('click', () => this.toggleFooter());
        document.getElementById('save-template-btn')?.addEventListener('click', () => this.save());
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
        this.renderCanvas();
        this.updateSlotProperties();
        document.getElementById('slot-properties').style.display = 'block';
    }

    deselectAll() {
        this.selectedSlot = null;
        document.getElementById('slot-properties').style.display = 'none';
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
