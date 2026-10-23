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

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BizError
from app.core.logging_setup import redact_credentials
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

# 显式清除通道清掉的字段（T02919）：只清凭证，保留地域/桶/CDN 等非敏感配置
CREDENTIAL_KEYS = ["cos_secret_id", "cos_secret_key"]

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
        """获取配置（前端展示用，SecretId/SecretKey 脱敏）并说明值从哪来。

        返回结构：
        {
            "configured": bool,           # 三项必填是否齐全（is_cos_configured 口径）
            "secret_id": "****xxxx"|"",   # 脱敏
            "secret_key": "****xxxx"|"",  # 脱敏
            "region": "ap-guangzhou",
            "bucket": "",
            "cdn_domain": "",
            # ---- INT-UX-04 / T02527 ----
            "loaded": bool,               # 本次是否真的读到了配置表
            "load_error": str | None,     # 读表失败原因（已脱敏，不含配置值）
            "updated_at": str | None,     # 表内最后一次入库修改时间；库里没记录就是 None
            "fallback_fields": [str],     # 这些字段的值是 .env 回落来的，不是库里存的
        }

        为什么要单独说来源：取不到库值时回落到 Settings 是有意为之（让 .env 配置可用），
        但「表是空的」与「表里有五个值」在旧响应里长得一模一样。管理员在第二种情况下
        点保存，会把 .env 的旧值静默固化进库；页面无从判定该不该禁存。
        """
        try:
            raw = await self.get_all_config()
            load_error = None
        except Exception as exc:
            # 完整异常只进日志；响应里给一个可读且已脱敏的原因（NFR-01 / NFR-05）
            logger.exception("COS 配置读取失败，前端将据 loaded=false 禁止保存")
            raw = {}
            load_error = f"{type(exc).__name__}: {redact_credentials(str(exc))[:200]}"

        settings = get_settings()
        fallback: list[str] = []

        def _get(name: str, key: str, settings_attr: str, default: str = "") -> str:
            val = raw.get(key)
            if val is not None:
                return val
            fallback.append(name)
            return str(getattr(settings, settings_attr, default))

        secret_id = _get("secret_id", "cos_secret_id", "COS_SECRET_ID")
        secret_key = _get("secret_key", "cos_secret_key", "COS_SECRET_KEY")
        region = _get("region", "cos_region", "COS_REGION", "ap-guangzhou")
        bucket = _get("bucket", "cos_bucket", "COS_BUCKET")
        cdn_domain = _get("cdn_domain", "cos_cdn_domain", "COS_CDN_DOMAIN")

        # 配置就绪口径与 is_cos_configured 保持一致：ID/KEY/BUCKET 三项齐全
        configured = bool(secret_id and secret_key and bucket)

        return {
            "configured": configured,
            "secret_id": _mask_key(secret_id),
            "secret_key": _mask_key(secret_key),
            "region": region,
            "bucket": bucket,
            "cdn_domain": cdn_domain,
            "loaded": load_error is None,
            "load_error": load_error,
            "updated_at": await self._latest_updated_at(only_if_loaded=load_error is None),
            "fallback_fields": fallback,
        }

    async def _latest_updated_at(self, only_if_loaded: bool) -> Optional[str]:
        """表内最后一次修改时间（本地 naive，与项目其余时间口径一致）。"""
        if not only_if_loaded:
            return None
        try:
            latest = (
                await self.db.execute(select(func.max(CosConfig.updated_at)))
            ).scalar_one_or_none()
        except Exception:
            logger.exception("COS 配置 updated_at 读取失败，按无修改时间处理")
            return None
        return latest.isoformat(timespec="seconds") if latest else None

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

        脱敏值（****开头）与空串**都表示「不修改」**，跳过写入；留空不等于清除 Key。
        换凭证直接填新值即可覆盖；要**作废**已存凭证走 `reset_credentials()`
        （`POST /cos/reset-config`，界面「清除凭证」），它会真正删行并把 Settings
        回退到 .env 默认值。保存后重置 COS 客户端缓存，使下一次调用用新凭证重新初始化。
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

    async def reset_credentials(self) -> dict:
        """清除已保存的 SecretId / SecretKey（T02919）。

        只删这两行，保留 region/bucket/cdn_domain——它们的值本身不是凭据，
        一起清掉会让「作废旧密钥」顺带把桶配置也废了。

        Settings 单例同步回退到 .env 默认值，并重建 COS 客户端缓存；
        只删库不回写内存的话，本进程仍拿旧凭证访问，看起来像「清除没生效」。

        返回清除后的配置（脱敏，含 loaded/fallback_fields 来源字段）。
        """
        for key in CREDENTIAL_KEYS:
            await self.db.execute(
                delete(CosConfig).where(CosConfig.config_key == key)
            )
        await self.db.commit()

        settings = get_settings()
        from app.config import Settings
        defaults = Settings()
        for key in CREDENTIAL_KEYS:
            attr = CONFIG_KEY_MAP.get(key)
            if attr:
                setattr(settings, attr, getattr(defaults, attr, ""))

        from app.cos.client import reset_cos_client
        reset_cos_client()

        logger.info("COS 凭证已清除 keys=%s", CREDENTIAL_KEYS)
        return await self.get_config_for_frontend()

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
            _ = await cos_client.list_objects_delimited(
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
