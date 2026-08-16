# -*- coding: utf-8 -*-
"""
Aqueous Whisper 图标后处理（色键去黑 + 圆形裁剪）

API 返回的图标背景为纯黑，与 macaron 亮主题冲突。
方案：基于"与黑色的距离"生成 alpha 蒙版——
- 接近黑色的像素（背景）→ 透明
- 远离黑色的像素（亮主体）→ 不透明
- 中间过渡区 → 半透明（Pillow GaussianBlur 羽化）
再叠加圆形裁剪限制范围，输出带透明背景的圆形头像。
图标主体可浮在登录页 macaron 背景之上。
"""
import numpy as np
from PIL import Image, ImageFilter

src = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon.png"
out = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon-round.png"

im = Image.open(src).convert("RGBA")
w, h = im.size
print(f"原始尺寸: {w}x{h}, 模式: {im.mode}")

arr = np.array(im).astype(np.float32)
rgb = arr[..., :3]

# 采样四角确认背景色
for name, (y, x) in {"左上": (2, 2), "右上": (2, -3),
                     "左下": (-3, 2), "右下": (-3, -3)}.items():
    print(f"  {name}: RGB{tuple(int(v) for v in rgb[y, x])}")

# 正方形裁剪（取中心）
size = min(w, h)
left = (w - size) // 2
top = (h - size) // 2
arr_sq = arr[top:top + size, left:left + size].copy()
rgb_sq = arr_sq[..., :3]

# === 色键蒙版：与黑色的距离 ===
# 距离 = sqrt(R²+G²+B²)，黑色=0，亮色大
dist_sq = np.sqrt(np.sum(rgb_sq ** 2, axis=2))
# 阈值：dist<55 全透明（纯黑背景），dist>130 全不透明（亮主体）
luma_alpha = np.clip((dist_sq - 55) / 75, 0, 1)
# 用 Pillow GaussianBlur 平滑蒙版（羽化），避免硬边
luma_img = Image.fromarray((luma_alpha * 255).astype(np.uint8), 'L')
luma_img = luma_img.filter(ImageFilter.GaussianBlur(1.5))
luma_alpha = np.array(luma_img).astype(np.float32) / 255

# === 圆形裁剪蒙版 ===
cx = cy = size / 2.0
yy, xx = np.ogrid[0:size, 0:size]
radial = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
radius = size / 2.0 - 2.0
circle_alpha = np.clip((radius - radial) / 2.0, 0, 1)

# 两蒙版相乘：圆形内 + 非黑色
final_alpha = luma_alpha * circle_alpha
arr_sq[..., 3] = (arr_sq[..., 3] * final_alpha).astype(np.uint8)

# 圆周极淡薄荷青描边（融入磨砂玻璃质感）
edge_ring = np.clip((radius + 1.5 - radial) / 1.5, 0, 1) * \
            np.clip((radial - radius + 1.5) / 1.5, 0, 1)
mint = np.array([126, 206, 193], dtype=np.float32)
blend = (edge_ring * final_alpha)[..., None] * 0.3
arr_sq[..., :3] = (arr_sq[..., :3] * (1 - blend) + mint * blend).astype(np.uint8)

im_final = Image.fromarray(arr_sq.astype(np.uint8), "RGBA")
im_final = im_final.filter(ImageFilter.GaussianBlur(0.5))
im_final.save(out, "PNG", optimize=True)

import os
print(f"OK -> 透明圆形头像: {out} ({size}x{size})")
print(f"文件大小: {round(os.path.getsize(out)/1024, 1)} KB")

alpha_arr = np.array(im_final)[..., 3]
transparent_ratio = np.sum(alpha_arr < 10) / alpha_arr.size
print(f"透明像素占比: {transparent_ratio*100:.1f}%（应主要为背景区）")
