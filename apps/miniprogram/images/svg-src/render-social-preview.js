// GitHub 社交预览图渲染脚本（T00397）
// 将 docs/assets-src/github-social-preview.svg 渲染为 1280x640 PNG
//
// 用法（在 svg-src 目录，复用本目录的 @resvg/resvg-js）：
//   node render-social-preview.js
//
// 中文字体：显式指向系统字体目录 + Microsoft YaHei，
// 避免默认字体缺 CJK 字形渲染成方框。

const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const scriptDir = __dirname;
// 仓库根：apps/miniprogram/images/svg-src -> 上四级
const repoRoot = path.resolve(scriptDir, '..', '..', '..', '..');
const srcPath = path.join(repoRoot, 'docs', 'assets-src', 'github-social-preview.svg');
const outPath = path.join(repoRoot, 'docs', 'github-social-preview.png');

const svg = fs.readFileSync(srcPath, 'utf-8');

const resvg = new Resvg(svg, {
  fitTo: { mode: 'width', value: 1280 },
  background: 'rgba(0,0,0,0)',
  font: {
    loadSystemFonts: true,
    fontDirs: ['C:\\Windows\\Fonts', '/usr/share/fonts', '/System/Library/Fonts'],
    defaultFontFamily: 'Microsoft YaHei',
  },
});

const png = resvg.render().asPng();
fs.writeFileSync(outPath, png);
const stat = fs.statSync(outPath);
console.log(`OK ${outPath} (${stat.size} bytes)`);
