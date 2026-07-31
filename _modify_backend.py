# -*- coding: utf-8 -*-
"""修改 17_xianyu 后端文件：app.py, auth.py, templates.py"""

def edit_file(path, old_text, new_text):
    """字面量替换文件内容，确保唯一匹配，保持原始换行符风格。"""
    with open(path, 'rb') as f:
        content = f.read()
    use_crlf = b'\r\n' in content
    text = content.decode('utf-8')
    text_lf = text.replace('\r\n', '\n')
    old_lf = old_text.replace('\r\n', '\n')
    new_lf = new_text.replace('\r\n', '\n')
    count = text_lf.count(old_lf)
    if count == 0:
        first_line = old_lf.split('\n')[0][:80]
        print(f"ERROR: 未找到目标文本 in {path}: {first_line}")
        return False
    if count > 1:
        first_line = old_lf.split('\n')[0][:80]
        print(f"ERROR: 找到 {count} 处匹配 in {path}: {first_line}")
        return False
    new_text_lf = text_lf.replace(old_lf, new_lf)
    new_text = new_text_lf.replace('\n', '\r\n') if use_crlf else new_text_lf
    with open(path, 'wb') as f:
        f.write(new_text.encode('utf-8'))
    print(f"OK: {path}")
    return True


BASE = r'd:\code\otherProjects\17_xianyu'
app_file = BASE + r'\src\xianyu_hunter\web\app.py'

# === app.py 替换 1: description 中的 /app/* → /xianyu/* ===
# 注意：原文用反引号包裹路径（Markdown 语法），不是双引号
assert edit_file(app_file, '`/app/*` SPA', '`/xianyu/*` SPA'), "app.py desc 失败"

# === app.py 替换 2: /app/docs 路由 → /docs ===
old_docs = '''    # /app/docs 重定向到 FastAPI 内置的 API 文档（docs_url=/api/docs）
    # 避免被下方 SPA catch-all 捕获后返回 index.html，导致前端路由跳回首页
    @app.get("/app/docs", include_in_schema=False)
    async def redirect_app_docs() -> RedirectResponse:
        return RedirectResponse(url="/api/docs", status_code=302)'''

new_docs = '''    # /docs 重定向到 FastAPI 内置的 API 文档（docs_url=/api/docs）
    # 避免被下方 SPA catch-all 捕获后返回 index.html，导致前端路由跳回首页
    @app.get("/docs", include_in_schema=False)
    async def redirect_app_docs() -> RedirectResponse:
        return RedirectResponse(url="/api/docs", status_code=302)'''

assert edit_file(app_file, old_docs, new_docs), "app.py docs 失败"

# === app.py 替换 3: _serve_spa_request 函数改造 ===
old_serve = '''def _serve_spa_request(spa_dir: Path, full_path: str) -> Response:
    """SPA catch-all 请求处理：静态文件直接返回，其余返回注入登录浮层的 index.html

    独立为模块级函数以降低 create_app 认知复杂度（S3776）。
    """
    if full_path:
        file_path = spa_dir / full_path
        if file_path.is_file():
            ext = file_path.suffix.lower()
            media_type = _SPA_MEDIA_TYPES.get(ext, "application/octet-stream")
            # assets/ 下是带 hash 的构建产物，可长期强缓存；其余路径禁缓存以保证 index.html 实时性
            headers = (
                {"Cache-Control": "public, max-age=31536000, immutable"}
                if full_path.startswith("assets/")
                else {"Cache-Control": "no-cache"}
            )
            return Response(content=file_path.read_bytes(), media_type=media_type, headers=headers)'''

new_serve = '''def _serve_spa_request(spa_dir: Path, full_path: str) -> Response:
    """SPA catch-all 请求处理：API 路径 404，剥离路径前缀后返回静态文件或 index.html

    Funnel 路径区分模式下，Funnel 剥离 /xianyu/ 前缀后后端收到不带前缀的路径；
    直接访问后端时浏览器按 base='/xianyu/' 请求前端路由（路径含 /xianyu/ 前缀）。
    独立为模块级函数以降低 create_app 认知复杂度（S3776）。
    """
    # API 路径不 fallback，返回 404 JSON（避免 API 404 被误返回 index.html）
    # 同时识别带 /xianyu/ 前缀的 API 路径（直接访问后端场景）
    if full_path.startswith(("api/", "xianyu/api/")):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    # 剥离 /xianyu/ 前缀：直接访问后端时浏览器按 base='/xianyu/' 请求前端路由
    rel_path = full_path[7:] if full_path.startswith("xianyu/") else full_path
    if rel_path:
        file_path = spa_dir / rel_path
        if file_path.is_file():
            ext = file_path.suffix.lower()
            media_type = _SPA_MEDIA_TYPES.get(ext, "application/octet-stream")
            # assets/ 下是带 hash 的构建产物，可长期强缓存；其余路径禁缓存以保证 index.html 实时性
            headers = (
                {"Cache-Control": "public, max-age=31536000, immutable"}
                if rel_path.startswith("assets/")
                else {"Cache-Control": "no-cache"}
            )
            return Response(content=file_path.read_bytes(), media_type=media_type, headers=headers)'''

assert edit_file(app_file, old_serve, new_serve), "app.py _serve_spa_request 失败"

# === app.py 替换 4: SPA catch-all + 根路径重定向 ===
old_catchall = '''    # SPA 可视化配置控制台（React 构建产物）
    # 访问 /app/* 时服务 SPA，支持客户端路由
    # vite base='/app/'，构建产物资源路径为 /app/assets/*
    # 注意：不使用 StaticFiles mount，因为 Windows 上 MIME 类型识别不准确
    #       统一由 spa_index catch-all 处理，确保 JS/CSS 等资源有正确的 Content-Type
    spa_dir = static_dir / "spa"
    if spa_dir.exists():
        @app.get("/app/{full_path:path}")
        async def spa_index(full_path: str) -> Response:
            """SPA catch-all：所有 /app/* 路径，静态文件直接返回，其余返回 index.html

            未登录时在 index.html 中注入登录引导浮层，
            引导用户跳转到 /app/login 完成登录后返回 /app。
            """
            return _serve_spa_request(spa_dir, full_path)

    # 根路径重定向到新版 SPA：旧版 SSR 已下线，所有用户访问 / 时跳转到 /app/
    @app.get("/", include_in_schema=False)
    async def redirect_to_spa() -> RedirectResponse:
        return RedirectResponse(url="/app/", status_code=302)'''

new_catchall = '''    # SPA 可视化配置控制台（React 构建产物）
    # Funnel 路径区分模式：Funnel 剥离 /xianyu/ 前缀后后端收到不带前缀的路径，
    # 因此 SPA catch-all 注册在根路径 /{full_path:path}，同时兼容直接访问后端场景。
    # vite base='/xianyu/'，构建产物资源路径为 /xianyu/assets/*
    # 注意：不使用 StaticFiles mount，因为 Windows 上 MIME 类型识别不准确
    #       统一由 spa_index catch-all 处理，确保 JS/CSS 等资源有正确的 Content-Type
    spa_dir = static_dir / "spa"
    if spa_dir.exists():
        # 根路径重定向到 /xianyu/（前端 SPA 入口）
        # 必须在 /{full_path:path} 之前注册，否则会被 catch-all 捕获
        @app.get("/", include_in_schema=False)
        async def redirect_to_spa() -> RedirectResponse:
            return RedirectResponse(url="/xianyu/", status_code=302)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_index(full_path: str) -> Response:
            """SPA catch-all：根路径接管所有未匹配的 GET 请求

            Funnel 剥离 /xianyu/ 前缀后后端收到不带前缀的路径；
            未登录时在 index.html 中注入登录引导浮层，
            引导用户跳转到 /xianyu/login 完成登录后返回 /xianyu/。
            """
            return _serve_spa_request(spa_dir, full_path)'''

assert edit_file(app_file, old_catchall, new_catchall), "app.py catchall 失败"

# === app.py 替换 5: SPA 登录浮层中的 /app/login ===
assert edit_file(app_file, 'href="/app/login">前往登录', 'href="/xianyu/login">前往登录'), "app.py login overlay href 失败"
assert edit_file(app_file, "indexOf('/app/login')", "indexOf('/xianyu/login')"), "app.py login overlay indexOf 失败"

# === app.py 替换 6: Swagger UI 导航链接 ===
assert edit_file(app_file, 'href="/app/" target="_blank">控制台', 'href="/xianyu/" target="_blank">控制台'), "app.py swagger console 失败"
assert edit_file(app_file, 'href="/app/about" target="_blank">📖 关于', 'href="/xianyu/about" target="_blank">📖 关于'), "app.py swagger about 失败"

print("=== app.py 修改完成 ===")


# === auth.py: 白名单 /app/ → /xianyu/ ===
auth_file = BASE + r'\src\xianyu_hunter\web\middleware\auth.py'

old_auth = '''    "/app/",                     # SPA 可视化控制台页面（API 调用仍需 token）'''

new_auth = '''    "/xianyu/",                  # SPA 可视化控制台页面（API 调用仍需 token）'''

assert edit_file(auth_file, old_auth, new_auth), "auth.py 失败"
print("=== auth.py 修改完成 ===")


# === templates.py: /app/confirm-buy → /xianyu/confirm-buy ===
tpl_file = BASE + r'\src\xianyu_hunter\modules\notifier\templates.py'

old_tpl = '''    前端 BrowserRouter basename="/app"，所以路径前缀必须包含 /app
    页面加载后展示商品快照与"确认抢单"按钮，点击调用 manual-takeover 接口
    """
    base = _get_web_base_url()
    return f"{base}/app/confirm-buy?task_id={task_id}&item_id={item_id}"'''

new_tpl = '''    前端 BrowserRouter basename="/xianyu"，所以路径前缀必须包含 /xianyu
    页面加载后展示商品快照与"确认抢单"按钮，点击调用 manual-takeover 接口
    """
    base = _get_web_base_url()
    return f"{base}/xianyu/confirm-buy?task_id={task_id}&item_id={item_id}"'''

assert edit_file(tpl_file, old_tpl, new_tpl), "templates.py 失败"
print("=== templates.py 修改完成 ===")

print("\n全部后端文件修改完成!")
