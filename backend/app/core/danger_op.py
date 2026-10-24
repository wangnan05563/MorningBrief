"""危险操作确认的单一口径（T02592）。

背景：数据库后台（db_admin）先改成了「服务端总开关 + 操作者手输确认文本」，
备份恢复（backup）却还留着旧口径——要求前端传一个固定令牌。两个口径并存的下场是确定的：
凡是「前端必须带密钥才能调」的接口，迟早有人把密钥写进 bundle 里，
于是一个后台按钮的权限就变成了全体登录用户的浏览器产物里的一段明文。

这里只放比较逻辑，不放开关本身：`server_token` 由各路由把自己的
`CONFIRM_TOKEN` 传进来，路由模块仍持有那个可被配置/测试替换的名字。
"""
import hmac

from app.core.exceptions import ParamError


def validate_danger_op(confirm_text: str | None, expected: str, server_token: str) -> None:
    """危险操作放行条件：服务端配置了 DB_ADMIN_CONFIRM_TOKEN（总开关，未配置即禁止），
    且操作者手输的确认文本与预期一致。令牌本身不再下发前端——
    前端内置固定令牌等于把删除/恢复权限打包进了浏览器产物。

    确认文本用的是**操作对象自身的名字**（表名 / 备份文件名），不是口令：
    它挡的是「没看清要动哪个对象就点了提交」，授权仍由 require_admin 负责。
    用 hmac.compare_digest 做常量时间比较，与 db_admin 落地时（commit `eccd084`）一致。
    """
    if not server_token:
        raise ParamError("服务器未配置 DB_ADMIN_CONFIRM_TOKEN，危险操作被禁止")
    if not hmac.compare_digest((confirm_text or "").strip(), expected):
        raise ParamError(f"确认文本不匹配，请输入 {expected}")
