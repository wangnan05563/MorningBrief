# -*- coding: utf-8 -*-
"""
Aqueous Whisper 图标 v2 后处理：圆形裁剪 + 透明背景

将 v2 图标的圆外区域设为透明，让图标真正"浮"在登录页背景之上。
"""
import numpy as np
from PIL import Image, ImageFilter

src = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon-v2.png"
out = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon.png"

im = Image.open(src).convert("RGBA")
w, h = im.size
arr = np.array(im).astype(np.float32)

# === 圆形 alpha 蒙版 ===
cy, cx = h / 2.0, w / 2.0
yy, xx = np.ogrid[0:h, 0:w]
radial = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
radius = min(w, h) / 2.0 - 1.0
circle_alpha = np.clip((radius - radial) / 2.0, 0, 1)

# 圆外清空 RGB，圆内保留
arr[..., 3] = arr[..., 3] * circle_alpha

im_final = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
im_final = im_final.filter(ImageFilter.GaussianBlur(0.4))  # 边缘羽化
im_final.save(out, "PNG", optimize=True)

import os
print(f"OK -> {out}")
print(f"尺寸: {im_final.size}")
print(f"文件大小: {round(os.path.getsize(out)/1024, 1)} KB")
alpha_arr = np.array(im_final)[..., 3]
transparent_ratio = np.sum(alpha_arr < 10) / alpha_arr.size
print(f"透明像素占比: {transparent_ratio*100:.1f}%")
