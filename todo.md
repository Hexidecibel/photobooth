# Todo

## Done
- [x] Core architecture (config, state machine, plugins, camera, MJPEG, WebSocket)
- [x] Kiosk frontend (8 screens, CSS theming, 14 languages)
- [x] Image pipeline (9 effects, layout engine, templates, chromakey, GIF/boomerang)
- [x] Hardware (GPIO buttons/LEDs, CUPS printing)
- [x] Sharing (QR codes, email, social, event gallery)
- [x] Admin panel (config editor, camera framing, analytics, backup, template editor)
- [x] Operations (watchdog, idle timeout, tunnel, offline resilience)
- [x] Branding (logo upload, CSS theming)
- [x] 9 layout templates + guest template picker
- [x] Pibooth config import
- [x] Deploy scripts (systemd, setup.sh, bin/sync)
- [x] Documentation (README, plugins, config, migration, deployment, templates)

## Backlog
- [ ] AI photo effects — post-capture AI editing (style transfer, background replacement, face filters, cartoonize, aging, etc.) using on-device models or API
- [ ] Video message mode — record short video clips with countdown
- [ ] Photo strip printing — 2 copies side-by-side on 4x6 for tear-apart strips
- [ ] Multi-booth management — control multiple booths from one admin panel
- [ ] Event presets — save/load complete event configs (template + theme + branding)
- [ ] Guest data collection — optional form before/after photo (name, email, survey)
- [ ] Photo approval workflow — operator reviews before printing
- [ ] Animated overlays — GIF/video overlays on the preview screen
- [ ] AI background removal — automatic subject extraction without green screen
- [ ] Face detection — auto-framing, smile detection trigger
