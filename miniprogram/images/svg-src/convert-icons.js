// SVG → PNG 转换脚本
// 使用 @resvg/resvg-js（纯 Rust 实现，无外部依赖）
//
// 用法：node convert-icons.js
// 在 svg-src 目录下执行

const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const scriptDir = __dirname;
const iconsDir = path.resolve(scriptDir, '..', 'icons');

if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// 图标生成配置：SVG 源 → PNG 输出 + 尺寸
const iconConfigs = [
  // tabBar 图标：81x81，圆角方形+渐变背景
  { svg: 'tab-today-active.svg',     out: 'tab-today-active.png',     size: 81 },
  { svg: 'tab-today-inactive.svg',   out: 'tab-today-inactive.png',   size: 81 },
  { svg: 'tab-history-active.svg',   out: 'tab-history-active.png',   size: 81 },
  { svg: 'tab-history-inactive.svg', out: 'tab-history-inactive.png', size: 81 },
  { svg: 'tab-profile-active.svg',   out: 'tab-profile-active.png',   size: 81 },
  { svg: 'tab-profile-inactive.svg', out: 'tab-profile-inactive.png', size: 81 },
  // 播放控制图标：48x48
  { svg: 'play.svg',                 out: 'play.png',                 size: 48 },
  { svg: 'pause.svg',                out: 'pause.png',                size: 48 },
  { svg: 'skip-back.svg',            out: 'skip-back.png',            size: 48 },
  { svg: 'skip-forward.svg',         out: 'skip-forward.png',         size: 48 },
  // 列表项小图标：32x32
  { svg: 'play-mini.svg',            out: 'play-mini.png',            size: 32 },
  // 状态切换图标：48x48
  { svg: 'favorite.svg',             out: 'favorite.png',             size: 48 },
  { svg: 'favorite-filled.svg',      out: 'favorite-filled.png',      size: 48 },
  { svg: 'moon.svg',                 out: 'moon.png',                 size: 48 },
  { svg: 'alarm.svg',                out: 'alarm.png',                size: 48 },
  // 顶部工具栏图标
  { svg: 'search.svg',               out: 'search.png',               size: 48 },
  { svg: 'chevron-right.svg',        out: 'chevron-right.png',        size: 32 },
  // 错误提示图标：48x48
  { svg: 'alert.svg',                out: 'alert.png',                size: 48 },
  // 时长前置小图标：32x32
  { svg: 'duration.svg',             out: 'duration.png',             size: 32 },
  // 空状态装饰图标：96x96
  { svg: 'headphones.svg',           out: 'headphones.png',           size: 96 },
  { svg: 'music.svg',                out: 'music.png',                size: 96 },
  { svg: 'newspaper.svg',            out: 'newspaper.png',            size: 96 },
  { svg: 'radio.svg',                out: 'radio.png',                size: 96 },
];

console.log(`SVG Source: ${scriptDir}`);
console.log(`PNG Output:  ${iconsDir}`);
console.log(`Total icons: ${iconConfigs.length}\n`);

let success = 0;
let failed = 0;

for (const cfg of iconConfigs) {
  const svgPath = path.join(scriptDir, cfg.svg);
  const outPath = path.join(iconsDir, cfg.out);

  if (!fs.existsSync(svgPath)) {
    console.warn(`  [MISS] ${cfg.svg}`);
    failed++;
    continue;
  }

  try {
    const svg = fs.readFileSync(svgPath);
    // 使用 Resvg 渲染 SVG 到 PNG，fitTo 限制最大尺寸
    const resvg = new Resvg(svg, {
      fitTo: { mode: 'width', value: cfg.size },
      background: 'rgba(0,0,0,0)',
    });
    const pngData = resvg.render().asPng();
    fs.writeFileSync(outPath, pngData);
    const stat = fs.statSync(outPath);
    console.log(`  [OK]   ${cfg.out} (${cfg.size}x${cfg.size}, ${stat.size} bytes)`);
    success++;
  } catch (e) {
    console.warn(`  [FAIL] ${cfg.out} - ${e.message}`);
    failed++;
  }
}

console.log(`\nSuccess: ${success}, Failed: ${failed}`);
