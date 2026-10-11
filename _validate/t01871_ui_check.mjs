// T01871 管理端档位展示的 UI 实测脚本（Playwright + 系统 Chrome，走内存里记的可用通道）。
// 目标：AI 服务页 TTS 标签内出现「成品输出档位」只读块，内容与后端接口一致。
// 前置：隔离后端（副本库 + APP_ROLE=api）在 8000、vite dev 在 5173、token 在 _validate/t01871_ui/tok.txt。
// 用法：node _validate/t01871_ui_check.mjs
import fs from 'node:fs';

// playwright 只装在 apps/admin-web 下，脚本在 _validate 里按绝对路径取
const { chromium } = await import(
  'file:///D:/code/otherProjects/20_News/apps/admin-web/node_modules/playwright/index.mjs'
);

const UI = 'D:/code/otherProjects/20_News/_validate/t01871_ui';
const token = fs.readFileSync(`${UI}/tok.txt`, 'utf8').trim();
const BASE = 'http://127.0.0.1:5173';

const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addCookies([{ name: 'admin_token', value: token, url: BASE }]);
await context.addInitScript(() => localStorage.setItem('admin_role', 'admin'));
const page = await context.newPage();

await page.goto(`${BASE}/ai-config`, { waitUntil: 'domcontentloaded' });
await page.getByRole('tab', { name: /TTS 语音合成/ }).waitFor({ timeout: 20000 });
console.log('URL_AFTER_LOAD=' + page.url());
await page.getByRole('tab', { name: /TTS 语音合成/ }).click();
const alert = page.locator('.profile-alert');
await alert.waitFor({ state: 'visible', timeout: 15000 });

const text = (await alert.innerText()).replace(/\s+/g, ' ');
console.log('ALERT_TEXT=' + text);
const chips = await page.locator('.profile-chip').allInnerTexts();
console.log('CHIPS=' + JSON.stringify(chips));
const editable = await page.locator('.profile-alert button, .profile-alert input, .profile-alert .el-select').count();
console.log('EDITABLE_CONTROLS=' + editable);
await page.screenshot({ path: `${UI}/ui_profile.png` });
await browser.close();
