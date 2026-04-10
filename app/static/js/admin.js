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
            container.innerHTML = '<div class="empty-state">No photos yet. Take some pictures!</div>';
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

        let html = '<form id="theme-form" class="config-form">';
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
        const container = document.getElementById('templates-content');
        container.innerHTML = '<div class="loading">Loading templates...</div>';

        try {
            const [tplRes, fxRes] = await Promise.all([
                fetch('/api/admin/templates'),
                fetch('/api/admin/effects'),
            ]);
            const templates = await tplRes.json();
            const effects = await fxRes.json();
            this.renderTemplates(templates.templates, effects.effects);
        } catch (e) {
            container.innerHTML = `<div class="error">Failed to load templates: ${e.message}</div>`;
        }
    }

    renderTemplates(templates, effects) {
        const container = document.getElementById('templates-content');

        let html = '<div class="config-section"><h3>Layout Templates</h3>';
        if (templates.length === 0) {
            html += '<div class="empty-state">No templates found. Add JSON templates to app/static/templates/</div>';
        } else {
            html += '<div class="template-list">';
            for (const t of templates) {
                html += `<div class="template-item">
                    <div class="template-icon">&#9638;</div>
                    <div class="template-name">${t}</div>
                </div>`;
            }
            html += '</div>';
        }
        html += '</div>';

        html += '<div class="config-section"><h3>Photo Effects</h3>';
        html += '<div class="effects-grid">';
        for (const fx of effects) {
            html += `<div class="effect-item">
                <div class="effect-name">${fx}</div>
            </div>`;
        }
        html += '</div>';
        html += '</div>';

        container.innerHTML = html;
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

const admin = new AdminPanel();
document.addEventListener('DOMContentLoaded', () => admin.init());
