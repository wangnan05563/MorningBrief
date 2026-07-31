# -*- coding: utf-8 -*-
"""修改 17_xianyu 前端文件：vite.config.ts, main.tsx, App.tsx, client.ts, useSSEChat.ts, Login/index.tsx, AccountSwitcher.tsx"""

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


def replace_all_file(path, old_text, new_text):
    """全局替换文件内容中的所有匹配，保持原始换行符风格。"""
    with open(path, 'rb') as f:
        content = f.read()
    use_crlf = b'\r\n' in content
    text = content.decode('utf-8')
    text_lf = text.replace('\r\n', '\n')
    old_lf = old_text.replace('\r\n', '\n')
    new_lf = new_text.replace('\r\n', '\n')
    count = text_lf.count(old_lf)
    if count == 0:
        print(f"ERROR (replace_all): 未找到目标文本 in {path}: {old_lf[:60]}")
        return False
    new_text_lf = text_lf.replace(old_lf, new_lf)
    new_text = new_text_lf.replace('\n', '\r\n') if use_crlf else new_text_lf
    with open(path, 'wb') as f:
        f.write(new_text.encode('utf-8'))
    print(f"OK (replace_all x{count}): {path}")
    return True


BASE = r'd:\code\otherProjects\17_xianyu\frontend'

# === 1. vite.config.ts ===
vite_file = BASE + r'\vite.config.ts'

# 1a. proxy 配置：/api → /xianyu/api，添加 rewrite
old_proxy = """    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },"""

new_proxy = """    proxy: {
      '/xianyu/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\\/xianyu/, ''),
      },
    },"""

assert edit_file(vite_file, old_proxy, new_proxy), "vite proxy 失败"

# 1b. 全局替换 /app/ → /xianyu/（base、PWA、注释等）
assert replace_all_file(vite_file, '/app/', '/xianyu/'), "vite /app/ 替换失败"

print("=== vite.config.ts 修改完成 ===")

# === 2. main.tsx: BrowserRouter basename ===
main_file = BASE + r'\src\main.tsx'
assert edit_file(main_file, '<BrowserRouter basename="/app">', '<BrowserRouter basename="/xianyu">'), "main.tsx 失败"
print("=== main.tsx 修改完成 ===")

# === 3. App.tsx: /app/m → /xianyu/m, /app/login → /xianyu/login ===
app_file = BASE + r'\src\App.tsx'

old_app = """  // 路径检测必须带 /app 前缀：SPA 挂载在 /app/ 下（BrowserRouter basename="/app"）
  // S7764：用 globalThis 替代 window
  // Navigate to="/m/" 必须带尾斜杠：父路由 <Route path="/m/*"> 的 splat 要求至少匹配 "/",
  // 不带尾斜杠的 /m 不会匹配 splat 路由，导致渲染 null（白屏）
  if (isMobile && !globalThis.location.pathname.startsWith('/app/m') && !globalThis.location.pathname.startsWith('/app/login')) {"""

new_app = """  // 路径检测必须带 /xianyu 前缀：SPA 挂载在 /xianyu/ 下（BrowserRouter basename="/xianyu"）
  // S7764：用 globalThis 替代 window
  // Navigate to="/m/" 必须带尾斜杠：父路由 <Route path="/m/*"> 的 splat 要求至少匹配 "/",
  // 不带尾斜杠的 /m 不会匹配 splat 路由，导致渲染 null（白屏）
  if (isMobile && !globalThis.location.pathname.startsWith('/xianyu/m') && !globalThis.location.pathname.startsWith('/xianyu/login')) {"""

assert edit_file(app_file, old_app, new_app), "App.tsx 失败"
print("=== App.tsx 修改完成 ===")

# === 4. client.ts: /app/login → /xianyu/login（两处+注释） ===
client_file = BASE + r'\src\api\client.ts'

old_client = """      // 避免在登录页本身触发跳转（防止死循环）
      // 路径匹配必须用 /app/login：SPA 挂载在 /app/ 下（vite base + BrowserRouter basename）
      const currentPath = globalThis.location.pathname + globalThis.location.search
      const isLoginPage = currentPath.startsWith('/app/login')
      if (!isLoginPage && !isRedirecting) {
        isRedirecting = true
        // 保存当前路径，登录后跳转回来
        const redirect = encodeURIComponent(currentPath)
        // 使用 replace 避免在历史记录中留下当前页面，
        // 防止用户后退回到已失效的认证态页面
        // 必须用 /app/login：浏览器原生跳转不走 react-router，
        // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
        globalThis.location.replace(`/app/login?redirect=${redirect}`)"""

new_client = """      // 避免在登录页本身触发跳转（防止死循环）
      // 路径匹配必须用 /xianyu/login：SPA 挂载在 /xianyu/ 下（vite base + BrowserRouter basename）
      const currentPath = globalThis.location.pathname + globalThis.location.search
      const isLoginPage = currentPath.startsWith('/xianyu/login')
      if (!isLoginPage && !isRedirecting) {
        isRedirecting = true
        // 保存当前路径，登录后跳转回来
        const redirect = encodeURIComponent(currentPath)
        // 使用 replace 避免在历史记录中留下当前页面，
        // 防止用户后退回到已失效的认证态页面
        // 必须用 /xianyu/login：浏览器原生跳转不走 react-router，
        // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
        globalThis.location.replace(`/xianyu/login?redirect=${redirect}`)"""

assert edit_file(client_file, old_client, new_client), "client.ts 失败"
print("=== client.ts 修改完成 ===")

# === 5. useSSEChat.ts: /app/login → /xianyu/login ===
sse_file = BASE + r'\src\pages\Chatbot\hooks\useSSEChat.ts'

old_sse = """          // 401：清除失效 token 并跳转登录页
          // 硬约束：401 必须触发重定向，不能静默吞掉
          // 必须用 /app/login：浏览器原生跳转不走 react-router，
          // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
          if (resp.status === 401) {
            localStorage.removeItem('xh_token')
            globalThis.location.href = '/app/login'
            return
          }"""

new_sse = """          // 401：清除失效 token 并跳转登录页
          // 硬约束：401 必须触发重定向，不能静默吞掉
          // 必须用 /xianyu/login：浏览器原生跳转不走 react-router，
          // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
          if (resp.status === 401) {
            localStorage.removeItem('xh_token')
            globalThis.location.href = '/xianyu/login'
            return
          }"""

assert edit_file(sse_file, old_sse, new_sse), "useSSEChat.ts 失败"
print("=== useSSEChat.ts 修改完成 ===")

# === 6. mobile/Login/index.tsx: /app/m/ → /xianyu/m/ ===
login_file = BASE + r'\src\mobile\pages\Login\index.tsx'
assert edit_file(login_file, "globalThis.location.href = '/app/m/'", "globalThis.location.href = '/xianyu/m/'"), "Login/index.tsx 失败"
print("=== mobile/Login/index.tsx 修改完成 ===")

# === 7. mobile/AccountSwitcher.tsx: /app/login → /xianyu/login ===
acct_file = BASE + r'\src\mobile\components\AccountSwitcher.tsx'

old_acct = """  // 路径 /app/login：SPA 挂在 /app/ 下，浏览器完整 URL 跳转绕过路由
  const handleLogout = useCallback(async () => {
    setSwitching(true)
    try {
      await authApi.logoutAccount()
      setOpen(false)
      globalThis.location.href = '/app/login'"""

new_acct = """  // 路径 /xianyu/login：SPA 挂在 /xianyu/ 下，浏览器完整 URL 跳转绕过路由
  const handleLogout = useCallback(async () => {
    setSwitching(true)
    try {
      await authApi.logoutAccount()
      setOpen(false)
      globalThis.location.href = '/xianyu/login'"""

assert edit_file(acct_file, old_acct, new_acct), "AccountSwitcher.tsx 失败"
print("=== mobile/AccountSwitcher.tsx 修改完成 ===")

print("\n全部前端文件修改完成!")
