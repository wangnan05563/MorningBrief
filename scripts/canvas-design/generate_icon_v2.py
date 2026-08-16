# -*- coding: utf-8 -*-
"""
Aqueous Whisper 品牌图标：磨砂玻璃声纹胶囊

设计理念：
- 圆形象征"声波凝结"的容器
- 磨砂玻璃质感：径向渐变 + 边缘高光，呼应系统整体磨砂玻璃卡片
- 内部声波同心圆：从中心向外辐射，象征信息向外传播
- 中心微光点：声源原点
- 配色与 macaron 主题一致：薄荷青 + 暖粉 + 瓷白

避免依赖 text_to_image API（之前返回占位文字"the image is generating..."），
改用 Pillow 直接程序化绘制，确保与设计哲学 100% 一致。
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# 输出尺寸：2x 超采样后降采样获得抗锯齿
SIZE_RAW = 1024
SIZE_OUT = 512

# 主题色（与 themes.scss macaron 一致）
MINT = (126, 206, 193)        # 薄荷青 #7ECEC1
MINT_LIGHT = (181, 234, 215)  # #B5EAD7
BLUSH = (255, 211, 224)       # 暖粉 #FFD3E0
BLUSH_DARK = (255, 154, 162)  # #FF9AA2
PORCELAIN = (249, 253, 251)   # 瓷白底 #F9FDFB
GLASS_WHITE = (255, 255, 255) # 高光
DEPTH_SHADOW = (45, 107, 95)  # 薄荷青深处 #2D6B5F


def make_radial(size, inner_rgb, outer_rgb, inner_r=0.0, outer_r=1.0, center=(0.5, 0.5)):
    """生成径向渐变 RGBA 数组"""
    H = W = size
    cy, cx = center[0] * H, center[1] * W
    yy, xx = np.ogrid[0:H, 0:W]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    t = np.clip((dist / max_dist - inner_r) / (outer_r - inner_r), 0, 1)
    arr = np.zeros((H, W, 4), dtype=np.float32)
    arr[..., 0] = inner_rgb[0] * (1 - t) + outer_rgb[0] * t
    arr[..., 1] = inner_rgb[1] * (1 - t) + outer_rgb[1] * t
    arr[..., 2] = inner_rgb[2] * (1 - t) + outer_rgb[2] * t
    arr[..., 3] = 255
    return arr


# === 第 1 层：瓷白磨砂玻璃底（圆形）===
# 整张画布先铺瓷白，然后后续只绘制圆形内部
arr = make_radial(SIZE_RAW, PORCELAIN, (235, 245, 240), 0.0, 0.95)

# === 第 2 层：圆形 mask（限定所有效果在圆内）===
yy, xx = np.ogrid[0:SIZE_RAW, 0:SIZE_RAW]
cy, cx = SIZE_RAW / 2, SIZE_RAW / 2
radial = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
radius = SIZE_RAW / 2 - 8
circle_mask = np.clip((radius - radial) / 3.0, 0, 1)[..., None].astype(np.float32)

# === 第 3 层：磨砂玻璃球体径向渐变（中心瓷白，边缘薄荷青）===
# 给圆形一个"凸起玻璃球"的体积感
sphere = make_radial(SIZE_RAW, (252, 254, 253), MINT_LIGHT, 0.0, 0.85)
# 边缘稍微深一点增加厚度
edge_dark = make_radial(SIZE_RAW, (0, 0, 0), (40, 80, 70), 0.75, 1.0)
edge_factor = (edge_dark[..., 0] / 255.0)[..., None] * 0.25
sphere = sphere * (1 - edge_factor)

# 用圆形 mask 限定到圆内
arr = arr * (1 - circle_mask) + sphere * circle_mask

# === 第 4 层：声波同心圆（从中心向外辐射的 5 圈）===
# 每圈透明度递减，模拟声波扩散衰减
draw_layer = np.zeros((SIZE_RAW, SIZE_RAW, 4), dtype=np.float32)
rings = [
    (0.10, MINT, 0.55),   # 最内圈
    (0.20, MINT, 0.40),
    (0.30, BLUSH_DARK, 0.32),
    (0.40, BLUSH_DARK, 0.22),
    (0.50, MINT, 0.14),
]
for r_norm, color, alpha in rings:
    r = r_norm * SIZE_RAW
    thickness = max(2, int(SIZE_RAW * 0.012))
    ring_mask = np.zeros((SIZE_RAW, SIZE_RAW), dtype=np.float32)
    # 软边环
    inner_edge = r - thickness / 2
    outer_edge = r + thickness / 2
    ring_mask = np.clip((outer_edge - radial) / 2.0, 0, 1) * np.clip((radial - inner_edge) / 2.0, 0, 1)
    ring_mask *= circle_mask[..., 0]
    for i, c in enumerate(color):
        draw_layer[..., i] += c * ring_mask * alpha
    draw_layer[..., 3] += ring_mask * alpha * 255

# 限制 alpha 不超过 255
draw_layer[..., 3] = np.clip(draw_layer[..., 3], 0, 255)
# 混合到主图（普通混合，draw_layer 已是预乘）
arr = arr * (1 - draw_layer[..., 3:4] / 255) + draw_layer

# === 第 5 层：中心声源（微光点）===
center_r = SIZE_RAW * 0.045
center_mask = np.clip((center_r - radial) / 2.0, 0, 1)[..., None]
center_glow = np.zeros((SIZE_RAW, SIZE_RAW, 4), dtype=np.float32)
center_glow[..., 0] = GLASS_WHITE[0]
center_glow[..., 1] = GLASS_WHITE[1]
center_glow[..., 2] = GLASS_WHITE[2]
center_glow[..., 3] = 255
arr = arr * (1 - center_mask * 0.95) + center_glow * center_mask * 0.95

# 中心点外圈薄荷青光环（增加层次）
ring_r = SIZE_RAW * 0.08
ring_thick = SIZE_RAW * 0.008
ring_mask = (
    np.clip((ring_r + ring_thick / 2 - radial) / 1.5, 0, 1) *
    np.clip((radial - ring_r + ring_thick / 2) / 1.5, 0, 1)
)[..., None]
for i, c in enumerate(MINT):
    arr[..., i] = arr[..., i] * (1 - ring_mask[..., 0] * 0.5) + c * ring_mask[..., 0] * 0.5

# === 第 6 层：左上方高光（玻璃球反射光）===
# 模拟从左上方照射的柔光
hl = np.zeros((SIZE_RAW, SIZE_RAW), dtype=np.float32)
hl_cy, hl_cx = SIZE_RAW * 0.35, SIZE_RAW * 0.35
hl_dist = np.sqrt((xx - hl_cx) ** 2 + (yy - hl_cy) ** 2)
hl_radius = SIZE_RAW * 0.32
hl = np.clip(1 - hl_dist / hl_radius, 0, 1) ** 2.5
hl_mask = hl * circle_mask[..., 0]
hl_mask_alpha = hl_mask[..., None].astype(np.float32)  # (H, W, 1)
white_3 = np.array([255.0, 255.0, 255.0], dtype=np.float32)  # (3,)
arr[..., :3] = arr[..., :3] * (1 - hl_mask_alpha * 0.25) + white_3 * hl_mask_alpha * 0.25

# === 第 7 层：圆形外描边（极淡薄荷青 + 阴影内圈）===
# 内圈阴影（增加深度）
shadow_r = radius - 2
shadow_mask = np.clip((shadow_r + 4 - radial) / 2.0, 0, 1) * np.clip((radial - shadow_r) / 2.0, 0, 1)
shadow_mask = shadow_mask * circle_mask[..., 0]
for i in range(3):
    arr[..., i] = arr[..., i] * (1 - shadow_mask * 0.15)

# === 第 8 层：外发光（让图标浮起）===
glow = (np.clip((radius + 30 - radial) / 30, 0, 1) * np.clip((radial - radius) / 5, 0, 1))[..., None]
mint_3 = np.array([float(MINT_LIGHT[0]), float(MINT_LIGHT[1]), float(MINT_LIGHT[2])], dtype=np.float32)
arr[..., :3] = arr[..., :3] * (1 - glow * 0.15) + mint_3 * glow * 0.15

# 转成 PIL 图像
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")

# 微模糊以模拟磨砂玻璃的漫反射
img = img.filter(ImageFilter.GaussianBlur(0.6))

# 2x 超采样后降采样获得抗锯齿（这里直接输出 1024，再用 LANCZOS 降采样到 512）
img = img.resize((SIZE_OUT, SIZE_OUT), Image.LANCZOS)

# 保存
out_path = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon-v2.png"
img.save(out_path, "PNG", optimize=True)

import os
print(f"OK -> {out_path}")
print(f"尺寸: {SIZE_OUT}x{SIZE_OUT}")
print(f"文件大小: {round(os.path.getsize(out_path)/1024, 1)} KB")
