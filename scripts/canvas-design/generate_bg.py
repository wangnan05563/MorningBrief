# -*- coding: utf-8 -*-
"""
Aqueous Whisper — 登录页背景艺术作品生成器

设计哲学：声波在磨砂玻璃后凝结成图谱。
- 2x 超采样保证线条与文字锐利（LANCZOS 降采样抗锯齿）
- 分层合成：模糊光晕（雾气） + 锐利声波图谱（精密） + 半透明雾气层（磨砂玻璃）
- macaron 粉彩：薄荷青 + 暖粉 + 米白，低饱和度高明度
- 系统化参考标记：同心圆声波、径向刻度、声谱密集标记、坐标标签
"""
import math
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# === 配置 ===
SS = 2  # 超采样倍数，最终降采样到 1920x1080
W, H = 1920 * SS, 1080 * SS
CX, CY = W // 2, H // 2

# macaron 色谱（与 themes.scss macaron 主题一致）
MINT = (126, 206, 193)          # --color-primary
MINT_LIGHT = (181, 234, 215)    # --color-primary-light
MINT_DARK = (45, 107, 95)       # --color-primary-dark
BLUSH = (255, 211, 224)         # --color-secondary
BLUSH_DARK = (255, 154, 162)    # --color-secondary-dark
PORCELAIN = (249, 253, 251)     # --color-bg
INK = (74, 85, 104)             # --color-text-primary


def radial_blob(size, color, falloff=2.5):
    """生成径向渐变圆盘：中心实色，边缘平滑透明。

    用 numpy 距离场计算，比 Pillow 逐像素绘制快两个数量级，
    falloff 指数控制光晕软硬度——2.5 接近真实漫射光。
    """
    r = size // 2
    y, x = np.ogrid[-r:r, -r:r]
    dist = np.sqrt(x * x + y * y) / r
    alpha = np.clip(1 - dist, 0, 1) ** falloff
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., 0] = color[0]
    arr[..., 1] = color[1]
    arr[..., 2] = color[2]
    arr[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def pseudo(i, seed=0):
    """确定性伪随机：基于 MD5，保证刷新后粒子位置稳定不闪烁。"""
    h = hashlib.md5(f"{i}-{seed}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


# === Layer 1：基底 + 模糊光晕（营造雾气氛围） ===
canvas = Image.new('RGBA', (W, H), PORCELAIN + (255,))

# 三块大光晕，不对称放置形成张力（左上重、右下轻、右上点缀）
canvas.alpha_composite(radial_blob(1000 * SS, MINT, 2.8),
                       (int(-220 * SS), int(-180 * SS)))
canvas.alpha_composite(radial_blob(880 * SS, BLUSH, 2.8),
                       (int(W - 680 * SS), int(H - 620 * SS)))
canvas.alpha_composite(radial_blob(640 * SS, MINT_LIGHT, 2.2),
                       (int(W * 0.58), int(-240 * SS)))
# 小块暖粉点缀（右下角呼应）
canvas.alpha_composite(radial_blob(420 * SS, BLUSH_DARK, 3.0),
                       (int(W * 0.82), int(H * 0.74)))


# === Layer 2：中心声波涟漪（锐利，同心圆指数衰减） ===
draw = ImageDraw.Draw(canvas, 'RGBA')

# 主声波：20 层同心圆，半径足够大以铺满画布，登录卡片只遮挡中心核
# 从中心向外指数衰减不透明度，近场亮、远场淡
for i in range(22):
    r = (55 + i * 44) * SS
    alpha = int(170 * (0.62 ** (i * 0.30)))
    alpha = max(alpha, 10)
    width = max(1, (3 - i // 7) * SS)
    draw.ellipse([CX - r, CY - r, CX + r, CY + r],
                 outline=MINT + (alpha,), width=width)

# 次级涟漪：暖粉色，更淡，错位营造层次
for i in range(9):
    r = (95 + i * 72) * SS
    alpha = int(72 * (0.6 ** (i * 0.38)))
    alpha = max(alpha, 7)
    ox, oy = 34 * SS, -22 * SS
    draw.ellipse([CX - r + ox, CY - r + oy, CX + r + ox, CY + r + oy],
                 outline=BLUSH_DARK + (alpha,), width=max(1, SS))


# === Layer 3：径向刻度系统（科学图谱风格） ===
# 内外双环刻度：内环密集（每 1°），外环稀疏（每 30° 长刻度 + 标签）
inner_r = 395 * SS
outer_r = 425 * SS
for deg in range(0, 360):
    rad = math.radians(deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    x1 = CX + inner_r * cos_r
    y1 = CY + inner_r * sin_r
    if deg % 30 == 0:
        # 主刻度：更长更亮
        x2 = CX + (outer_r + 26 * SS) * cos_r
        y2 = CY + (outer_r + 26 * SS) * sin_r
        alpha = 135
        width = max(1, 2 * SS)
    elif deg % 10 == 0:
        x2 = CX + (outer_r + 12 * SS) * cos_r
        y2 = CY + (outer_r + 12 * SS) * sin_r
        alpha = 78
        width = max(1, SS)
    else:
        x2 = CX + outer_r * cos_r
        y2 = CY + outer_r * sin_r
        alpha = 38
        width = 1
    draw.line([x1, y1, x2, y2], fill=MINT_DARK + (alpha,), width=width)


# === Layer 4：声谱密集标记（径向短线，模拟频谱采样） ===
# 在内环内侧分布密集短线，长度用正弦调制避免均匀单调
for i in range(120):
    angle = math.radians(i * 3 + 1.5)
    length = (18 + 22 * (0.5 + 0.5 * math.sin(i * 0.7))) * SS
    r1 = 300 * SS
    r2 = r1 + length
    x1 = CX + r1 * math.cos(angle)
    y1 = CY + r1 * math.sin(angle)
    x2 = CX + r2 * math.cos(angle)
    y2 = CY + r2 * math.sin(angle)
    alpha = 55 + int(40 * (0.5 + 0.5 * math.cos(i * 1.3)))
    draw.line([x1, y1, x2, y2], fill=MINT + (alpha,), width=max(1, SS))


# === Layer 5：中心十字准星 + 核心点 ===
cross_len = 18 * SS
cross_alpha = 95
for x1, y1, x2, y2 in [
    (CX - cross_len, CY, CX - 4 * SS, CY),
    (CX + 4 * SS, CY, CX + cross_len, CY),
    (CX, CY - cross_len, CX, CY - 4 * SS),
    (CX, CY + 4 * SS, CX, CY + cross_len),
]:
    draw.line([x1, y1, x2, y2], fill=MINT_DARK + (cross_alpha,), width=max(1, SS))
draw.ellipse([CX - 3 * SS, CY - 3 * SS, CX + 3 * SS, CY + 3 * SS],
             fill=MINT_DARK + (145,))


# === Layer 6：漂浮粒子（确定性散布，避开中心声波区） ===
particle_positions = []
for i in range(60):
    # 避开中心声波区域（半径 480px 内不放粒子，保持中心纯净）
    for attempt in range(8):
        px = pseudo(i * 8 + attempt, 10) * W
        py = pseudo(i * 8 + attempt, 11) * H
        if math.hypot(px - CX, py - CY) > 490 * SS:
            break
    ps = (2.5 + pseudo(i, 12) * 7) * SS
    pa = int(35 + pseudo(i, 13) * 75)
    color = MINT if i % 4 != 0 else BLUSH_DARK
    draw.ellipse([px - ps, py - ps, px + ps, py + ps], fill=color + (pa,))
    particle_positions.append((px, py))


# === Layer 7：磨砂玻璃雾气层（半透明白 + 轻微模糊） ===
# 关键：这层让底层色彩透出但被雾化，营造磨砂玻璃质感
haze = Image.new('RGBA', (W, H), (255, 255, 255, 40))
haze = haze.filter(ImageFilter.GaussianBlur(2 * SS))
canvas.alpha_composite(haze)

# 暗角：用 numpy 全画布一次性径向距离场（中心透明、四角微暗）
# 比 radial_blob 大数组 + composite 快十倍
yy, xx = np.ogrid[0:H, 0:W]
dist = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2)
max_dist = math.hypot(CX, CY)
# 仅边缘 50% 以外开始变暗，指数 1.5 让过渡柔和
vig_alpha = np.clip((dist / max_dist - 0.55) / 0.45, 0, 1) ** 1.5 * 42
vig_arr = np.zeros((H, W, 4), dtype=np.uint8)
vig_arr[..., 3] = vig_alpha.astype(np.uint8)
canvas.alpha_composite(Image.fromarray(vig_arr, 'RGBA'))


# === Layer 8：极简文字标签（科学图谱参考标记） ===
draw = ImageDraw.Draw(canvas, 'RGBA')
font_label = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 13 * SS)
font_micro = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 10 * SS)
font_title = ImageFont.truetype("C:/Windows/Fonts/segoeuil.ttf", 11 * SS)
font_coord = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 11 * SS)

# 度数标签（四个主方位）
for deg, label in [(0, "0°"), (90, "90°"), (180, "180°"), (270, "270°")]:
    rad = math.radians(deg)
    r = outer_r + 48 * SS
    x = CX + r * math.cos(rad)
    y = CY + r * math.sin(rad)
    bbox = draw.textbbox((0, 0), label, font=font_coord)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw / 2, y - th / 2), label, font=font_coord,
              fill=MINT_DARK + (115,))

# 左上角：作品标题（字间距大，低饱和）
draw.text((64 * SS, 56 * SS), "A Q U E O U S   W H I S P E R",
          font=font_title, fill=MINT_DARK + (118,))
draw.text((64 * SS, 78 * SS), "SPECIMEN · 001 / FROSTED RESONANCE",
          font=font_micro, fill=INK + (92,))

# 右下角：图例参考
draw.text((W - 300 * SS, H - 66 * SS), "FIG. 01 · SPECTROGRAM",
          font=font_label, fill=MINT_DARK + (138,))
draw.text((W - 300 * SS, H - 44 * SS), "FREQ 432Hz · AMP 0.62 · 04:32",
          font=font_micro, fill=INK + (102,))

# 右上角：坐标参考
draw.text((W - 200 * SS, 56 * SS), "Lat 31.23°N", font=font_micro, fill=INK + (88,))
draw.text((W - 200 * SS, 74 * SS), "Lng 121.47°E", font=font_micro, fill=INK + (88,))

# 左下角：刻度参考线 + 标签
scale_y = H - 66 * SS
draw.line([64 * SS, scale_y, 164 * SS, scale_y],
          fill=MINT_DARK + (125,), width=max(1, SS))
for i in range(5):
    sx = 64 * SS + i * 25 * SS
    draw.line([sx, scale_y - 4 * SS, sx, scale_y + 4 * SS],
              fill=MINT_DARK + (125,), width=max(1, SS))
draw.text((64 * SS, scale_y + 10 * SS),
          "0      25      50      75     100 ms",
          font=font_micro, fill=INK + (88,))


# === 最终：降采样到 1920x1080（LANCZOS 抗锯齿） ===
final = canvas.resize((1920, 1080), Image.LANCZOS)
out_path = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-bg.png"
final.convert('RGB').save(out_path, 'PNG', optimize=True)
print(f"OK -> 1920x1080 saved: {out_path}")
