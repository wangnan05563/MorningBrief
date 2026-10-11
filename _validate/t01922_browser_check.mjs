// T01922 播放端实测（本机可用通道）：用系统 Chrome 的媒体栈逐个起播档位物料，
// 记录 MediaError / duration / seek 后是否能继续推进。
// ⚠ 口径诚实：这是 **Chromium 桌面内核** 的实测结果，不等于任务要求的 微信小程序/iOS/Android 三端；
//   它只能回答「码流本身是否可被常见解码器起播」，真机结论仍缺。
// 前置：本机静态服务 http://127.0.0.1:8123/ 指向 _validate/t01922_pack
import fs from 'node:fs';

// playwright 只装在 apps/admin-web 下，脚本在 _validate/ 里 → 必须按绝对路径 import
// （node 的裸标识符解析看脚本位置，不看 cwd）
const { chromium } = await import(
  'file:///D:/code/otherProjects/20_News/apps/admin-web/node_modules/playwright/index.mjs'
);

const OUT = 'D:/code/otherProjects/20_News/_validate/t01922_browser_results.json';
const BASE = 'http://127.0.0.1:8123';
const FILES = [
  'A0_published_copy.mp3',
  'A_baseline_128k_44100.mp3',
  'B_standard_64k_32000.mp3',
  'C_quality_96k_44100.mp3',
  'D_lean_48k_32000.mp3',
  'E_lsf_64k_24000.mp3',
  'F_aac_64k_32000.m4a',
  'G_hls_aac_64k_32000/playlist.m3u8',
];

const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
const page = await browser.newPage();
await page.goto(`${BASE}/A0_published_copy.mp3`, { waitUntil: 'domcontentloaded' }).catch(() => {});

const results = [];
for (const f of FILES) {
  const url = `${BASE}/${f}`;
  const head = await page.evaluate(async (u) => {
    try {
      const r = await fetch(u, { method: 'GET', headers: { Range: 'bytes=0-1' } });
      return {
        status: r.status,
        content_type: r.headers.get('content-type'),
        accept_ranges: r.headers.get('accept-ranges'),
        content_range: r.headers.get('content-range'),
      };
    } catch (e) {
      return { fetch_error: String(e) };
    }
  }, url);

  const play = await page.evaluate(
    (u) =>
      new Promise((resolve) => {
        const a = new Audio();
        const rec = {
          started: false,
          duration: null,
          error_code: null,
          error_msg: null,
          seek_ok: false,
          advanced_ms: 0,
          can_play_type: a.canPlayType(u.endsWith('.m3u8') ? 'application/vnd.apple.mpegurl' : ''),
        };
        let t0 = null;
        const finish = () => {
          a.pause();
          resolve(rec);
        };
        const timer = setTimeout(() => {
          rec.error_msg = rec.error_msg || 'timeout(12s)';
          finish();
        }, 12000);
        a.addEventListener('loadedmetadata', () => {
          rec.started = true;
          rec.duration = a.duration;
          try {
            a.currentTime = Math.min(30, (a.duration || 60) / 2);
          } catch (e) {
            rec.error_msg = 'seek: ' + String(e).slice(0, 80);
          }
        });
        a.addEventListener('timeupdate', () => {
          if (t0 === null && a.currentTime > 0) {
            rec.seek_ok = a.currentTime > 5;
            t0 = a.currentTime;
            setTimeout(() => {
              rec.advanced_ms = Math.round((a.currentTime - t0) * 1000);
              clearTimeout(timer);
              finish();
            }, 1500);
          }
        });
        a.addEventListener('error', () => {
          rec.error_code = a.error ? a.error.code : -1;
          clearTimeout(timer);
          finish();
        });
        a.src = u;
        a.play().catch((e) => {
          rec.error_msg = rec.error_msg || String(e).slice(0, 120);
        });
      }),
    url,
  );
  results.push({ file: f, http: head, play });
  console.log(`${f} -> started=${play.started} dur=${play.duration} err=${play.error_code} seek=${play.seek_ok} adv=${play.advanced_ms}ms`);
}

fs.writeFileSync(OUT, JSON.stringify({ ua: await page.evaluate(() => navigator.userAgent), results }, null, 2));
await browser.close();
