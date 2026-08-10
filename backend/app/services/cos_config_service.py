"""云端 COS 配置管理服务（V1.5 新增）。

职责（与 ai_config_service 对齐）：
1. 配置 CRUD（从 SQLite cos_config 表读写）
2. 配置热更新（同步覆盖 Settings 内存单例，无需重启）
3. API Key 脱敏（SecretId / SecretKey 返回 ****xxxx，前端回传脱敏值视为未修改）
4. 连接测试（列举桶对象验证凭证与 Bucket 可达性）
5. 启动时加载（apply_config_to_settings 覆盖 Settings 单例）

桥接策略：cos_config 表的 config_key 与 Settings 类 COS_* 字段一一对应，
启动时调用 apply_config_to_settings() 将数据库配置覆盖到 Settings 单例，
使现有的 cos_client.py / uploader.py 等代码无需修改即可读取最新配置。

SecretId / SecretKey 为敏感字段：明文存库（SQLite 文件级安全），GET 接口脱敏，
POST 回传脱敏值（**** 开头）视为未修改，保留库中既有明文。
"""
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BizError
from app.models.cos_config import CosConfig

logger = logging.getLogger(__name__)

# ---- 配置项与 Settings 字段的映射 ----
# key = cos_config 表的 config_key，value = Settings 类的属性名
CONFIG_KEY_MAP = {
    "cos_secret_id": "COS_SECRET_ID",
    "cos_secret_key": "COS_SECRET_KEY",
    "cos_region": "COS_REGION",
    "cos_bucket": "COS_BUCKET",
    "cos_cdn_domain": "COS_CDN_DOMAIN",
}

# 需要脱敏的配置项（SecretId / SecretKey 类）
SENSITIVE_KEYS = {"cos_secret_id", "cos_secret_key"}

# 默认值（DB 无记录时回退到 Settings 默认值；这里给前端一个展示基线）
DEFAULT_KEYS = {
    "cos_region": "ap-guangzhou",
}


def _mask_key(key: str) -> str:
    """敏感字段脱敏：保留后 4 位，前缀 ****。"""
    if not key:
        return ""
    return f"****{key[-4:]}" if len(key) > 4 else "****"


def _is_masked(value: str) -> bool:
    """判断前端回传值是否为脱敏值（未修改）。"""
    return bool(value) and value.startswith("****")


class CosConfigService:
    """云端 COS 配置管理服务。

    所有方法注入 AsyncSession，与项目其他 service 保持一致的调用方式。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 配置读取 ----

    async def get_all_config(self) -> dict[str, str]:
        """读取全部 COS 配置，返回 {config_key: config_value} 字典。"""
        result = await self.db.execute(select(CosConfig))
        rows = result.scalars().all()
        return {row.config_key: row.config_value for row in rows}

    async def get_config_value(self, key: str) -> Optional[str]:
        """读取单个配置项。"""
        result = await self.db.execute(
            select(CosConfig.config_value).where(CosConfig.config_key == key)
        )
        return result.scalar_one_or_none()

    async def get_config_for_frontend(self) -> dict:
        """获取配置（前端展示用，SecretId/SecretKey 脱敏）。

        返回结构：
        {
            "configured": bool,           # 三项必填是否齐全（is_cos_configured 口径）
            "secret_id": "****xxxx"|"",   # 脱敏
            "secret_key": "****xxxx"|"",  # 脱敏
            "region": "ap-guangzhou",
            "bucket": "",
            "cdn_domain": "",
        }
        """
        raw = await self.get_all_config()
        settings = get_settings()

        def _get(key: str, settings_attr: str, default: str = "") -> str:
            val = raw.get(key)
            if val is not None:
                return val
            return str(getattr(settings, settings_attr, default))

        secret_id = _get("cos_secret_id", "COS_SECRET_ID")
        secret_key = _get("cos_secret_key", "COS_SECRET_KEY")
        region = _get("cos_region", "COS_REGION", "ap-guangzhou")
        bucket = _get("cos_bucket", "COS_BUCKET")
        cdn_domain = _get("cos_cdn_domain", "COS_CDN_DOMAIN")

        # 配置就绪口径与 is_cos_configured 保持一致：ID/KEY/BUCKET 三项齐全
        configured = bool(secret_id and secret_key and bucket)

        return {
            "configured": configured,
            "secret_id": _mask_key(secret_id),
            "secret_key": _mask_key(secret_key),
            "region": region,
            "bucket": bucket,
            "cdn_domain": cdn_domain,
        }

    # ---- 配置更新 ----

    async def update_config(
        self,
        secret_id: str = "",
        secret_key: str = "",
        region: str = "ap-guangzhou",
        bucket: str = "",
        cdn_domain: str = "",
    ) -> None:
        """保存 COS 配置到 SQLite 并热更新 Settings 单例。

        脱敏值（****开头）视为未修改，跳过；空字符串视为清除 Key。
        保存后重置 COS 客户端缓存，使下一次调用用新凭证重新初始化。
        """
        updates: dict[str, str] = {
            "cos_region": region or "ap-guangzhou",
            "cos_bucket": bucket or "",
            "cos_cdn_domain": cdn_domain or "",
        }
        # SecretId / SecretKey：脱敏值跳过（保留库中原值）；新值/空值直接使用
        if secret_id and not _is_masked(secret_id):
            updates["cos_secret_id"] = secret_id
        if secret_key and not _is_masked(secret_key):
            updates["cos_secret_key"] = secret_key

        if not updates:
            return

        for key, value in updates.items():
            await self._upsert_config(key, value)

        await self.db.commit()

        # 热更新 Settings 内存单例
        self._apply_to_settings(updates)

        # 重置 COS 客户端缓存：凭证/地域/桶变更后必须重建客户端，否则沿用旧连接
        from app.cos.client import reset_cos_client
        reset_cos_client()

        logger.info("COS 配置已更新 keys=%s", list(updates.keys()))

    def _apply_to_settings(self, updates: dict[str, str]) -> None:
        """将更新同步到 Settings 内存单例。"""
        settings = get_settings()
        for key, value in updates.items():
            attr = CONFIG_KEY_MAP.get(key)
            if not attr:
                continue
            setattr(settings, attr, value)

    async def _upsert_config(self, key: str, value: str) -> None:
        """插入或更新单个配置项。"""
        existing = await self.db.execute(
            select(CosConfig).where(CosConfig.config_key == key)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.config_value = value
        else:
            self.db.add(CosConfig(config_key=key, config_value=value))

    # ---- 启动时加载 ----

    async def apply_config_to_settings(self) -> None:
        """启动时从 SQLite 加载 COS 配置覆盖到 Settings 单例。

        在 main.py lifespan 中调用，使 .env 中的配置可被前端修改覆盖。
        """
        raw = await self.get_all_config()
        if not raw:
            return

        settings = get_settings()
        applied = []
        for key, value in raw.items():
            attr = CONFIG_KEY_MAP.get(key)
            if not attr:
                continue
            setattr(settings, attr, value)
            applied.append(key)

        if applied:
            logger.info("从 SQLite 加载 COS 配置 %d 项: %s", len(applied), applied)

    # ---- 连接测试 ----

    async def test_connection(self) -> dict:
        """测试 COS 连接（列举桶根对象验证凭证与 Bucket 可达性）。

        与前端保存解耦：测试的是当前生效配置（DB 覆盖后的 Settings 单例）。
        未配置时直接返回失败提示，避免创建空客户端抛出晦涩异常。
        """
        from app.cos.client import is_cos_configured, cos_client

        if not is_cos_configured():
            return {
                "success": False,
                "message": "COS 未配置：请先填写 SecretId / SecretKey / Bucket",
            }

        settings = get_settings()
        try:
            # 列举桶根（最多 1 个对象即可验证可读），用分隔符模拟目录避免大桶全量列举
            resp = await cos_client.list_objects_delimited(
                Prefix="", Delimiter="/", MaxKeys=1
            )
            # 能拿到响应即说明凭证与 Bucket 有效
            return {
                "success": True,
                "message": "连接成功",
                "bucket": settings.COS_BUCKET,
                "region": settings.COS_REGION,
            }
        except Exception as e:  # NOSONAR 连接测试需把任意异常转可读提示
            err_msg = str(e)
            logger.warning("COS 连接测试失败: %s", err_msg)
            # 常见错误语义化
            if "AccessDenied" in err_msg or "403" in err_msg:
                return {"success": False, "message": "凭证无效或无 Bucket 访问权限（AccessDenied）"}
            if "NoSuchBucket" in err_msg or "404" in err_msg:
                return {"success": False, "message": f"存储桶不存在: {settings.COS_BUCKET}"}
            if "SecretId" in err_msg or "SecretKey" in err_msg:
                return {"success": False, "message": "SecretId / SecretKey 无效"}
            return {"success": False, "message": f"连接失败: {err_msg[:200]}"}
