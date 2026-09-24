#!/usr/bin/env python3
"""
Script generador del banner oficial para Open Graph y Twitter Cards de RTMS.
Genera la imagen 'site/brand_preview.png' a 1200x630 píxeles optimizada para:
- WhatsApp / Telegram / Discord / Slack (rich link preview cards)
- Twitter / X (summary_large_image)
- Facebook / LinkedIn (Open Graph preview)

Requisitos:
    pip install playwright
    (Utiliza el motor Chromium de Microsoft Edge preinstalado en Windows)
"""

import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: Requiere playwright. Instálalo con: pip install playwright")
    sys.exit(1)

HTML_CARD_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    width: 1200px;
    height: 630px;
    background-color: #060913;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #f3f4f6;
    overflow: hidden;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 44px 52px;
  }

  .grid-bg {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image:
      linear-gradient(to right, rgba(56, 189, 248, 0.04) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(56, 189, 248, 0.04) 1px, transparent 1px);
    background-size: 32px 32px;
    pointer-events: none;
  }

  .glow-top-left {
    position: absolute;
    top: -140px;
    left: -120px;
    width: 650px;
    height: 650px;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.22) 0%, transparent 65%);
    pointer-events: none;
  }
  .glow-bottom-right {
    position: absolute;
    bottom: -160px;
    right: -100px;
    width: 750px;
    height: 750px;
    background: radial-gradient(circle, rgba(20, 184, 166, 0.26) 0%, transparent 65%);
    pointer-events: none;
  }
  .glow-center {
    position: absolute;
    top: 100px;
    right: 220px;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(30, 58, 138, 0.25) 0%, transparent 70%);
    pointer-events: none;
  }

  .border-frame {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: 1px solid rgba(56, 189, 248, 0.15);
    box-shadow: inset 0 0 60px rgba(0, 0, 0, 0.8);
    pointer-events: none;
  }

  .left-col {
    position: relative;
    z-index: 10;
    width: 520px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 18px;
  }

  .brand-header {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .brand-logo {
    width: 48px;
    height: 48px;
    filter: drop-shadow(0 0 16px rgba(56, 189, 248, 0.5));
  }
  .brand-name {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: #ffffff;
  }
  .version-tag {
    font-size: 12.5px;
    font-weight: 700;
    padding: 3px 10px;
    background: rgba(20, 184, 166, 0.16);
    color: #2dd4bf;
    border: 1px solid rgba(20, 184, 166, 0.45);
    border-radius: 20px;
    font-family: 'SFMono-Regular', Consolas, monospace;
    letter-spacing: 0.5px;
  }
  .os-tag {
    font-size: 12px;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
  }
  .os-tag svg {
    color: #38bdf8;
  }

  .hero-headline {
    font-size: 38px;
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -0.03em;
    color: #ffffff;
  }
  .gradient-text {
    background: linear-gradient(135deg, #38bdf8 0%, #2dd4bf 55%, #34d399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .target-platforms {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
  }
  .target-title {
    font-size: 19px;
    font-weight: 700;
    color: #e2e8f0;
  }
  .platform-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 5px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    color: #7dd3fc;
  }

  .hero-sub {
    font-size: 15px;
    line-height: 1.5;
    color: #94a3b8;
    max-width: 480px;
  }
  .hero-sub strong {
    color: #f1f5f9;
    font-weight: 600;
  }

  .features-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
    margin-top: 2px;
  }
  .feature-pill {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(56, 189, 248, 0.12);
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .feature-icon-box {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
  }
  .feature-text {
    font-size: 12px;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1.25;
  }
  .feature-sub {
    font-size: 10.5px;
    color: #64748b;
    font-weight: 500;
  }

  .footer-meta {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 2px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .url-badge {
    display: flex;
    align-items: center;
    gap: 7px;
    color: #38bdf8;
    font-size: 13.5px;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-weight: 700;
  }
  .badge-tag {
    font-size: 11px;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.05);
    padding: 3px 9px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.09);
    font-weight: 500;
  }

  .right-col {
    position: relative;
    z-index: 10;
    width: 550px;
  }

  .window-mockup {
    background: #0c1220;
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 12px;
    box-shadow:
      0 25px 60px -10px rgba(0, 0, 0, 0.85),
      0 0 45px rgba(20, 184, 166, 0.22),
      inset 0 1px 0 rgba(255, 255, 255, 0.12);
    overflow: hidden;
  }

  .window-header {
    background: #111a2f;
    padding: 11px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .window-dots {
    display: flex;
    gap: 7px;
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
  .dot.red { background: #ef4444; }
  .dot.yellow { background: #f59e0b; }
  .dot.green { background: #10b981; }

  .window-title {
    font-size: 12px;
    font-weight: 700;
    color: #cbd5e1;
    letter-spacing: 0.3px;
  }
  .live-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    font-weight: 800;
    color: #34d399;
    background: rgba(16, 185, 129, 0.16);
    padding: 2.5px 8px;
    border-radius: 12px;
    border: 1px solid rgba(16, 185, 129, 0.4);
    letter-spacing: 0.4px;
  }
  .pulse-dot {
    width: 6px;
    height: 6px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 6px #10b981;
  }

  .telemetry-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    background: rgba(15, 23, 42, 0.95);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    padding: 9px 12px;
    gap: 8px;
  }
  .hud-stat {
    text-align: center;
    border-right: 1px solid rgba(255, 255, 255, 0.07);
  }
  .hud-stat:last-child {
    border-right: none;
  }
  .hud-label {
    font-size: 9.5px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  .hud-val {
    font-size: 12.5px;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-weight: 800;
    color: #38bdf8;
    margin-top: 1px;
  }

  .cards-container {
    padding: 13px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .cam-card {
    background: #131c31;
    border: 1px solid rgba(20, 184, 166, 0.28);
    border-left: 3.5px solid #14b8a6;
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .cam-card.alt {
    border-left-color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.28);
  }

  .cam-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .cam-info {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .cam-indicator {
    width: 8px;
    height: 8px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
  }
  .cam-title {
    font-size: 13.5px;
    font-weight: 700;
    color: #ffffff;
  }
  .cam-tag {
    font-size: 10px;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
  }
  .cam-badge-live {
    font-size: 10.5px;
    font-weight: 800;
    color: #10b981;
    background: rgba(16, 185, 129, 0.16);
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }

  .cam-meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px 12px;
    font-size: 11px;
    margin-top: 2px;
  }
  .meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #94a3b8;
  }
  .meta-value {
    color: #f1f5f9;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-weight: 700;
  }
  .meta-srt {
    grid-column: span 2;
    background: rgba(6, 10, 19, 0.6);
    padding: 5px 10px;
    border-radius: 5px;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 10.5px;
    color: #38bdf8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    border: 1px solid rgba(56, 189, 248, 0.2);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .srt-prefix {
    color: #2dd4bf;
    font-weight: 700;
  }

  .standby-card {
    background: rgba(15, 23, 42, 0.45);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    color: #64748b;
  }
</style>
</head>
<body>

  <div class="grid-bg"></div>
  <div class="glow-top-left"></div>
  <div class="glow-bottom-right"></div>
  <div class="glow-center"></div>
  <div class="border-frame"></div>

  <!-- LEFT: HERO BRANDING -->
  <div class="left-col">
    <div class="brand-header">
      <img src="isotype.svg" class="brand-logo" alt="RTMS Logo">
      <div>
        <div style="display: flex; align-items: center; gap: 9px;">
          <span class="brand-name">RTMS</span>
        </div>
        <div class="os-tag">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.949-1.801"/>
          </svg>
          <span>Servidor Nativo para Windows 10 / 11</span>
        </div>
      </div>
    </div>

    <div>
      <h1 class="hero-headline">
        Streaming Multicámara<br>
        <span class="gradient-text">de Ultra-Baja Latencia</span>
      </h1>
      <div class="target-platforms">
        <span class="target-title">Directo a tu producción</span>
        <span class="platform-badge">OBS Studio</span>
        <span class="platform-badge">vMix</span>
      </div>
    </div>

    <p class="hero-sub">
      Captura dispositivos DirectShow con aceleración GPU (NVENC/QSV/AMF) y emite flujos independientes mediante <strong>SRT & MediaMTX</strong> con latencia &lt;100 ms y reconexión PnP automática.
    </p>

    <div class="features-grid">
      <div class="feature-pill">
        <div class="feature-icon-box" style="color: #38bdf8;">⚡</div>
        <div>
          <div class="feature-text">&lt; 100 ms Latencia</div>
          <div class="feature-sub">SRT / UDP Local</div>
        </div>
      </div>
      <div class="feature-pill">
        <div class="feature-icon-box" style="color: #10b981;">🎮</div>
        <div>
          <div class="feature-text">Aceleración GPU</div>
          <div class="feature-sub">NVENC • QSV • AMF</div>
        </div>
      </div>
      <div class="feature-pill">
        <div class="feature-icon-box" style="color: #f59e0b;">🔄</div>
        <div>
          <div class="feature-text">Hotplug USB PnP</div>
          <div class="feature-sub">Reconexión en &lt;5s</div>
        </div>
      </div>
      <div class="feature-pill">
        <div class="feature-icon-box" style="color: #a855f7;">🛡️</div>
        <div>
          <div class="feature-text">100% Red Local</div>
          <div class="feature-sub">Cero telemetría • DPAPI</div>
        </div>
      </div>
    </div>

    <div class="footer-meta">
      <div class="url-badge">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="2" y1="12" x2="22" y2="12"></line>
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
        </svg>
        <span>fjyarsky.github.io/RTMS</span>
      </div>
      <span class="badge-tag">Open Source (MIT)</span>
      <span class="badge-tag">ZIP Portable</span>
    </div>
  </div>

  <!-- RIGHT: LIVE INTERFACE MOCKUP -->
  <div class="right-col">
    <div class="window-mockup">
      <div class="window-header">
        <div class="window-dots">
          <div class="dot red"></div>
          <div class="dot yellow"></div>
          <div class="dot green"></div>
        </div>
        <div class="window-title">RTMS Control Panel</div>
        <div class="live-status">
          <div class="pulse-dot"></div>
          SRT ACTIVE
        </div>
      </div>

      <div class="telemetry-bar">
        <div class="hud-stat">
          <div class="hud-label">CPU</div>
          <div class="hud-val">4.2%</div>
        </div>
        <div class="hud-stat">
          <div class="hud-label">GPU (NVML)</div>
          <div class="hud-val" style="color: #2dd4bf;">11% • RTX</div>
        </div>
        <div class="hud-stat">
          <div class="hud-label">RED TOTAL</div>
          <div class="hud-val">14.8 Mbps</div>
        </div>
        <div class="hud-stat">
          <div class="hud-label">STREAMS</div>
          <div class="hud-val" style="color: #34d399;">2 Activos</div>
        </div>
      </div>

      <div class="cards-container">
        <!-- CAM 1 -->
        <div class="cam-card">
          <div class="cam-top">
            <div class="cam-info">
              <div class="cam-indicator"></div>
              <span class="cam-title">Logitech C920 Pro HD</span>
              <span class="cam-tag">DirectShow</span>
            </div>
            <span class="cam-badge-live">● EN VIVO</span>
          </div>
          <div class="cam-meta-grid">
            <div class="meta-item">
              <span>Resolución:</span>
              <span class="meta-value">1080p @ 60 FPS</span>
            </div>
            <div class="meta-item">
              <span>Encoder:</span>
              <span class="meta-value">h264_nvenc</span>
            </div>
            <div class="meta-srt">
              <span class="srt-prefix">SRT:</span>
              <span>srt://127.0.0.1:8890?streamid=read:cam_1</span>
            </div>
          </div>
        </div>

        <!-- CAM 2 -->
        <div class="cam-card alt">
          <div class="cam-top">
            <div class="cam-info">
              <div class="cam-indicator" style="background: #38bdf8; box-shadow: 0 0 8px #38bdf8;"></div>
              <span class="cam-title">Elgato Cam Link 4K</span>
              <span class="cam-tag">HDMI</span>
            </div>
            <span class="cam-badge-live" style="color: #38bdf8; background: rgba(56, 189, 248, 0.16);">● EN VIVO</span>
          </div>
          <div class="cam-meta-grid">
            <div class="meta-item">
              <span>Resolución:</span>
              <span class="meta-value">1080p @ 60 FPS</span>
            </div>
            <div class="meta-item">
              <span>Encoder:</span>
              <span class="meta-value">h264_nvenc</span>
            </div>
            <div class="meta-srt">
              <span class="srt-prefix" style="color: #38bdf8;">SRT:</span>
              <span>srt://127.0.0.1:8890?streamid=read:cam_2</span>
            </div>
          </div>
        </div>

        <!-- CAM 3 STANDBY -->
        <div class="standby-card">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 7px; height: 7px; background: #64748b; border-radius: 50%;"></div>
            <span style="font-weight: 600; color: #94a3b8;">NVIDIA Broadcast (Virtual IA)</span>
          </div>
          <span style="font-size: 10.5px; color: #64748b; font-family: monospace; font-weight: 600;">REPOSO (0% CPU/GPU)</span>
        </div>
      </div>
    </div>
  </div>

</body>
</html>
"""


def generate():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    site_dir = os.path.join(root_dir, "site")
    temp_html = os.path.join(site_dir, "_temp_og_card.html")
    output_png = os.path.join(site_dir, "brand_preview.png")

    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(HTML_CARD_TEMPLATE)

    file_url = "file:///" + temp_html.replace("\\", "/")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            page.goto(file_url)
            page.wait_for_timeout(1000)
            screenshot_bytes = page.screenshot()
            browser.close()

        with open(output_png, "wb") as f:
            f.write(screenshot_bytes)
        print(f"Social card generado exitosamente en: {output_png} (1200x630 px)")
    finally:
        if os.path.exists(temp_html):
            os.remove(temp_html)


if __name__ == "__main__":
    generate()
