"""C 端账号数据自助删除（T02788 / J98，裁决记录见 MTask T02788）。

背景：隐私政策第七条原写「要求删除个人信息（退出登录即可）」，而退出登录只清本机
（`pages/profile/profile.js` 的 logout 仅调 localData/downloadStore 的 clearByOpenid），
服务端一条都不删，且此前没有任何删除接口。T02513 先把文案改成如实的人工通道，
本单把承诺变成功能：接口 + 小程序入口 + 文案改回自助表述。

身份只从 token 解析（User.id → openid）。请求体只认 `confirm`——即便有人塞
openid/user_id 进来，业务也不会读它，越权删除在入口处就没有落点。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError
from app.core.response import success
from app.core.write_gate import write_lock
from app.database import get_db
from app.services.account_service import AccountPurgeService, retention_policy
from app.services.user_service import UserService, get_user_openid

router = APIRouter(prefix="/api/v1/account", tags=["C端-账号"])


class PurgeRequest(BaseModel):
    """删除确认体。除 confirm 外的字段不参与鉴权与寻址（Pydantic 默认忽略多余字段）。"""

    confirm: bool = False


@router.get("/data")
async def preview_my_data(
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回「删除我的数据」确认框需要的影响条数与备份保留口径。

    文案里的条数必须来自真实删除口径：前端自己数不出来（它只知道本机副本），
    写死一个数字则会在数据变动后变成第二处谎言。
    """
    openid = await get_user_openid(db, user.user_id)
    counts = await AccountPurgeService(db).summarize(user.user_id, openid)
    return success(data={"counts": counts, "retention": retention_policy()})


@router.delete("/data")
async def purge_my_data(
    req: PurgeRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除本人名下的全部服务器数据，并清理云端镜像。

    执行顺序是本单的核心约束（裁决 2）：数据库事务提交**之后**才删 COS。
    反过来做的话，COS 抖动会让接口在「库已删」之后返回失败，用户重试时
    又拿到「用户不存在」——一个不可逆操作不该留下这种半途状态。
    """
    if not req.confirm:
        raise BizError(code=400, message="删除个人数据需二次确认：请求体需带 confirm=true")

    openid = await get_user_openid(db, user.user_id)
    svc = AccountPurgeService(db)
    async with write_lock():
        counts = await svc.purge(user.user_id, openid)
        svc.add_audit(openid, counts)
        await db.commit()

    cos_result = await svc.purge_cos(user.user_id, openid)

    # 删号后这张 token 必须立刻失效：user 行已不存在，但拉黑能保证其它读接口
    # 在 get_user_openid 之前就被 401 挡住，而不是先撞一个 404。
    await UserService(db).logout(user.jti, user.exp, user.user_id)

    # user:openid 缓存若不清，同进程内后续请求仍能凭旧缓存拿到已删除的 openid；
    # 收藏列表缓存同理，避免二次登录（同 openid 重新注册）后读到旧列表。
    await cache.delete(f"user:openid:{user.user_id}")
    await cache.delete_pattern(f"fav:list:{openid}:*")

    return success(
        data={
            "deleted": counts,
            "cos": cos_result,
            "message": "本人服务器数据已删除，云端镜像已清理",
        }
    )
