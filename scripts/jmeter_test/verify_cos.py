"""COS 凭证验证脚本。

验证项：
1. is_cos_configured() 返回 True
2. COS 客户端能成功连接
3. 上传一个小测试文件
4. 拼接出的 URL 可公网访问
5. 清理测试文件
"""
import asyncio
import sys
from pathlib import Path

# 用项目 venv 运行，确保能 import app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# 切换工作目录到 backend，让 .env 被正确加载
import os
os.chdir(BACKEND_DIR)

from app.config import get_settings
from app.workflow.tts.uploader import is_cos_configured, upload_to_cos


async def main() -> int:
    print("=" * 60)
    print("COS 凭证验证")
    print("=" * 60)

    # 1. 验证配置检测
    settings = get_settings()
    print(f"\n[1] 配置检测")
    print(f"    COS_SECRET_ID: {settings.COS_SECRET_ID[:20]}...")
    print(f"    COS_SECRET_KEY: {'*' * len(settings.COS_SECRET_KEY)}")
    print(f"    COS_BUCKET: {settings.COS_BUCKET}")
    print(f"    COS_REGION: {settings.COS_REGION}")
    print(f"    COS_CDN_DOMAIN: '{settings.COS_CDN_DOMAIN}' (空=用 COS 默认域名)")
    print(f"    is_cos_configured(): {is_cos_configured()}")

    if not is_cos_configured():
        print("\n[FAIL] COS 未正确配置，请检查 .env")
        return 1

    # 2. 上传测试文件
    print(f"\n[2] 上传测试文件")
    test_key = "test/_cos_verify.txt"
    test_content = b"MorningBrief COS verify test - delete me"
    try:
        url = await upload_to_cos(test_content, test_key)
        print(f"    上传成功")
        print(f"    返回 URL: {url}")
    except Exception as e:
        print(f"    [FAIL] 上传失败: {e}")
        return 1

    # 3. 验证 URL 可公网访问
    print(f"\n[3] 验证 URL 公网可访问")
    import urllib.request
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read()
            print(f"    HTTP Status: {status}")
            print(f"    Content-Length: {len(body)} bytes")
            print(f"    Content 匹配: {body == test_content}")
            if status != 200 or body != test_content:
                print(f"    [FAIL] 响应不匹配")
                return 1
    except Exception as e:
        print(f"    [FAIL] 访问失败: {e}")
        return 1

    # 4. 预期 URL 格式
    expected_url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{test_key}"
    print(f"\n[4] URL 格式验证")
    print(f"    实际: {url}")
    print(f"    预期: {expected_url}")
    print(f"    匹配: {url == expected_url}")

    # 5. 清理测试文件
    print(f"\n[5] 清理测试文件")
    try:
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
        client = CosS3Client(config)
        client.delete_object(Bucket=settings.COS_BUCKET, Key=test_key)
        print(f"    清理成功: {test_key}")
    except Exception as e:
        print(f"    [WARN] 清理失败（不影响功能）: {e}")

    print("\n" + "=" * 60)
    print("✅ COS 凭证验证全部通过")
    print("=" * 60)
    print("\n配置摘要：")
    print(f"  Bucket: {settings.COS_BUCKET}")
    print(f"  Region: {settings.COS_REGION}")
    print(f"  默认域名: https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com")
    print(f"\n下一步：")
    print(f"  1. 小程序后台 → 开发管理 → 服务器域名 → downloadFile 合法域名")
    print(f"     添加: https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com")
    print(f"  2. 重启后端服务，下次工作流合成音频会自动上传到 COS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
