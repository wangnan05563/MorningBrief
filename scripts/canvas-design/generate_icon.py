# -*- coding: utf-8 -*-
"""
Aqueous Whisper 图标生成器

参考 awesome-nano-banana 案例：
- Case 46 (Happy Capsule Creation) — 抽象胶囊容器概念
- Case 81 (3D Translucent Glass Transformation) — 半透明玻璃质感
- Case 37 (Pastel Power 3D ADS) — macaron 粉彩色调
- Case 100 的提示词风格 — 详细描述质感、光影、构图

融合当前主题：薄荷青 + 暖粉 macaron + 磨砂玻璃 + 声波涟漪 + 新闻播客定位
替代原登录页的具象机器人 SVG，改为抽象治愈系声纹胶囊。
"""
import urllib.request
import urllib.parse
import json
import os
import sys

# nano-banana 风格提示词：详细描述质感、光影、构图、情绪
# 强调磨砂玻璃 + 声波 + macaron 粉彩，无机器人/人脸特征，纯抽象治愈
prompt = (
    "A minimalist 3D illustration of a translucent frosted glass sound capsule, "
    "floating on a bright luminous pastel background with a soft light gradient "
    "from pale mint teal to pale blush pink. The background must be bright, airy, "
    "and luminous white-pastel, never dark, never black. The capsule is a smooth "
    "rounded pebble shape, made of semi-transparent frosted glass with a matte "
    "surface, containing delicate concentric sound ripples glowing gently inside "
    "like a captured whisper. Soft diffused lighting from the upper left creates "
    "a gentle inner glow in mint teal, with a faint blush pink halo bleeding at "
    "the edges. Fine light refractions on the frosted surface. No face, no robot, "
    "no character features, purely abstract and contemplative. Tiny engraved "
    "linear reference marks on the surface suggest a scientific specimen. "
    "Centered composition with vast negative space, handcrafted museum-quality "
    "finish, healing and serene atmosphere. Bright pastel palette, low "
    "saturation, high luminance, white background. No text, no watermark, no logo."
)

encoded = urllib.parse.quote(prompt)
url = (
    "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image"
    f"?prompt={encoded}&image_size=square_hd"
)

out_path = r"d:\code\otherProjects\20_News\canvas-design\aqueous-whisper-icon.png"

print("Requesting icon generation...")
print(f"URL length: {len(url)} chars")

req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'image/*,application/json;q=0.9,*/*;q=0.8',
})
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        content_type = resp.headers.get('Content-Type', '')
        data = resp.read()
        print(f"Content-Type: {content_type}")
        print(f"Response size: {len(data)} bytes")

        if content_type.startswith('image/'):
            # 直接返回图片二进制
            with open(out_path, 'wb') as f:
                f.write(data)
            print(f"OK -> icon saved: {out_path}")
        elif 'json' in content_type:
            # 返回 JSON（可能含图片 URL）
            result = json.loads(data.decode('utf-8'))
            print("JSON response:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:1500])
            # 尝试从 JSON 提取图片 URL
            img_url = None
            if isinstance(result, dict):
                for key in ('url', 'image_url', 'data', 'result', 'image'):
                    val = result.get(key)
                    if isinstance(val, str) and val.startswith('http'):
                        img_url = val
                        break
                if not img_url and isinstance(result.get('data'), dict):
                    for key in ('url', 'image_url'):
                        val = result['data'].get(key)
                        if isinstance(val, str) and val.startswith('http'):
                            img_url = val
                            break
            if img_url:
                print(f"Downloading from: {img_url}")
                with urllib.request.urlopen(img_url, timeout=120) as r2:
                    img_data = r2.read()
                with open(out_path, 'wb') as f:
                    f.write(img_data)
                print(f"OK -> icon saved: {out_path} ({len(img_data)} bytes)")
            else:
                print("ERROR: could not extract image URL from JSON")
                sys.exit(1)
        else:
            # 未知类型，尝试当作图片保存
            print(f"Unknown content type, raw first 200 bytes: {data[:200]}")
            sys.exit(1)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
