# -*- coding: utf-8 -*-
"""修改 17_xianyu TailscaleProvider 相关文件：tunnel_providers.py, tunnel_service.py, yaml_config.py"""
import sys

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
tp_file = BASE + r'\src\xianyu_hunter\web\services\tunnel_providers.py'

# === 1a. 类注释 + 添加 __init__ + _normalize_path_prefix ===
old1 = '''class TailscaleProvider(TunnelProvider):
    """Tailscale Funnel：使用已安装并登录的 Tailscale 提供固定 ts.net 地址。

    Tailscale CLI 只负责配置系统后台服务，因此运行状态不能用子进程存活判断，
    必须通过 ``tailscale funnel status --json`` 查询。
    """

    binary_name = "tailscale.exe"
    download_urls: list[str] = []

    def _ensure_binary(self) -> Path:'''

new1 = '''class TailscaleProvider(TunnelProvider):
    """Tailscale Funnel：使用已安装并登录的 Tailscale 提供固定 ts.net 地址。

    Tailscale CLI 只负责配置系统后台服务，因此运行状态不能用子进程存活判断，
    必须通过 ``tailscale funnel status --json`` 查询。

    多应用路径区分模式：通过 path_prefix 在同一节点的 443 端口下分配独立路径，
    Funnel 自动剥离前缀转发给后端，实现单节点多应用共存。
    """

    binary_name = "tailscale.exe"
    download_urls: list[str] = []

    def __init__(self, local_port: int, binary_path: str = "", path_prefix: str = ""):
        """初始化 Tailscale provider。

        path_prefix 非空时启用多应用路径区分模式：
        - start 用 --set-path 注册路径，URL 为 https://{host}{path_prefix}
        - stop 不调用 funnel off，避免关闭其他应用的 Funnel 路径
        """
        super().__init__(local_port, binary_path)
        # 规范化路径前缀：确保以 / 开头、以 / 结尾，空字符串表示根路径模式（旧行为）
        self._path_prefix = self._normalize_path_prefix(path_prefix)

    @staticmethod
    def _normalize_path_prefix(prefix: str) -> str:
        """规范化路径前缀为 /xxx/ 形式，空字符串表示根路径模式。"""
        if not prefix:
            return ""
        p = prefix.strip()
        if not p.startswith("/"):
            p = "/" + p
        if not p.endswith("/"):
            p = p + "/"
        return p

    def _ensure_binary(self) -> Path:'''

assert edit_file(tp_file, old1, new1), "1a 失败"

# === 1b. _run_cli 添加 encoding/errors ===
old2 = '''    def _run_cli(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
        if self._binary_path is None:
            self._binary_path = self._ensure_binary()
        result = subprocess.run(
            [str(self._binary_path), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )'''

new2 = '''    def _run_cli(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
        if self._binary_path is None:
            self._binary_path = self._ensure_binary()
        # 显式指定 UTF-8 解码：tailscale CLI 输出固定为 UTF-8，
        # 中文 Windows 默认用 GBK 解码会导致含非 ASCII 字符的 JSON 解析失败
        result = subprocess.run(
            [str(self._binary_path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )'''

assert edit_file(tp_file, old2, new2), "1b 失败"

# === 1c. _funnel_url_from_status 从 @staticmethod 改为实例方法 + Handlers 检查 ===
old3 = '''    @staticmethod
    def _funnel_url_from_status(data: dict) -> str | None:
        allow_funnel = data.get("AllowFunnel")
        if not isinstance(allow_funnel, dict):
            return None
        for endpoint, enabled in allow_funnel.items():
            if not enabled:
                continue
            host = str(endpoint).rsplit(":", 1)[0].rstrip(".")
            if host.lower().endswith(".ts.net"):
                return f"https://{host}"
        return None'''

new3 = '''    def _funnel_url_from_status(self, data: dict) -> str | None:
        """从 funnel status --json 提取当前应用的公网 URL。

        多应用路径模式下，URL 包含 path_prefix（如 https://host/xianyu/）；
        根路径模式下，URL 为 https://host（旧行为）。
        通过匹配 Handlers 中的路径前缀确认当前应用的 Funnel 配置是否存在。
        """
        allow_funnel = data.get("AllowFunnel")
        if not isinstance(allow_funnel, dict):
            return None
        # 提取 ts.net 主机名
        host: str | None = None
        for endpoint, enabled in allow_funnel.items():
            if not enabled:
                continue
            h = str(endpoint).rsplit(":", 1)[0].rstrip(".")
            if h.lower().endswith(".ts.net"):
                host = h
                break
        if not host:
            return None

        # 路径区分模式：检查 Handlers 中是否存在自己的路径前缀
        if self._path_prefix:
            web = data.get("Web", {})
            handlers = {}
            if isinstance(web, dict):
                # Web 的 key 格式为 "host:443"，取第一个匹配的
                for _endpoint, cfg in web.items():
                    if isinstance(cfg, dict) and "Handlers" in cfg:
                        handlers = cfg["Handlers"]
                        break
            if not isinstance(handlers, dict) or self._path_prefix not in handlers:
                return None
            return f"https://{host}{self._path_prefix}"

        # 根路径模式（旧行为）：URL 不含路径前缀
        return f"https://{host}"'''

assert edit_file(tp_file, old3, new3), "1c 失败"

# === 1d. _start_funnel_process 构造 funnel 命令（包含 --set-path） ===
old4 = '''    def _start_funnel_process(self) -> subprocess.Popen:
        """启动 funnel 子进程：--bg 后台运行，--yes 跳过交互确认"""
        return subprocess.Popen(
            [str(self._binary_path), "funnel", "--bg", "--yes", f"http://127.0.0.1:{self._local_port}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )'''

new4 = '''    def _start_funnel_process(self) -> subprocess.Popen:
        """启动 funnel 子进程：--bg 后台运行，--yes 跳过交互确认

        路径区分模式用 --set-path 注册路径前缀，Funnel 自动剥离前缀转发给后端。
        """
        funnel_args = ["funnel", "--bg", "--yes"]
        if self._path_prefix:
            funnel_args += ["--set-path", self._path_prefix]
        funnel_args.append(f"http://127.0.0.1:{self._local_port}")
        return subprocess.Popen(
            [str(self._binary_path), *funnel_args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )'''

assert edit_file(tp_file, old4, new4), "1d 失败"

# === 1e. _read_funnel_output 中成功标志的 URL 构造加 path_prefix ===
old5 = '''            # 检测成功标志：funnel 已建立
            if "Funnel started" in stripped or "listening on" in stripped.lower():
                self._public_url = f"https://{dns_name}"
                logger.info(f"[tailscale] Funnel 已建立: {self._public_url}")
                return True'''

new5 = '''            # 检测成功标志：funnel 已建立
            if "Funnel started" in stripped or "listening on" in stripped.lower():
                self._public_url = f"https://{dns_name}{self._path_prefix}"
                logger.info(f"[tailscale] Funnel 已建立: {self._public_url}")
                return True'''

assert edit_file(tp_file, old5, new5), "1e 失败"

# === 1f. stop 方法在路径模式下不调用 funnel off ===
old6 = '''    def stop(self) -> None:
        # 关闭 Funnel：tailscale funnel off 即可，不需要 --https=443 端口参数
        # 捕获异常不抛出：stop 失败不应阻塞配置保存或服务关闭等调用方操作
        # timeout=10s：funnel off 是本地命令应很快返回，
        # Tailscale 服务未运行时命令会卡住等待连接，10s 足够判断
        if self._binary_path is not None:
            try:
                self._run_cli("funnel", "off", timeout=10)
            except Exception as e:
                logger.warning(f"[tailscale] 关闭 Funnel 失败（忽略）: {e}")
        self._public_url = None
        logger.info("[tailscale] Funnel 已关闭")'''

new6 = '''    def stop(self) -> None:
        # 路径区分模式：不调用 funnel off，避免关闭其他应用的 Funnel 路径
        # Tailscale 无移除单个路径的命令，停止后路径配置保留（访问会连接失败），
        # 重新启动应用后 --set-path 幂等更新配置自动恢复
        if self._path_prefix:
            self._public_url = None
            logger.info(f"[tailscale] 路径区分模式：保留 Funnel 配置 {self._path_prefix}")
            return

        # 根路径模式（旧行为）：关闭整个 Funnel
        # 捕获异常不抛出：stop 失败不应阻塞配置保存或服务关闭等调用方操作
        # timeout=10s：funnel off 是本地命令应很快返回，
        # Tailscale 服务未运行时命令会卡住等待连接，10s 足够判断
        if self._binary_path is not None:
            try:
                self._run_cli("funnel", "off", timeout=10)
            except Exception as e:
                logger.warning(f"[tailscale] 关闭 Funnel 失败（忽略）: {e}")
        self._public_url = None
        logger.info("[tailscale] Funnel 已关闭")'''

assert edit_file(tp_file, old6, new6), "1f 失败"

print("\n=== TailscaleProvider 修改完成 ===")


# === 2. tunnel_service.py: 传 path_prefix 参数给 TailscaleProvider ===
ts_file = BASE + r'\src\xianyu_hunter\web\services\tunnel_service.py'

old_ts = '''        kwargs: dict = {"binary_path": cfg.binary_path}
        if provider_name == "cpolar":
            kwargs["authtoken"] = cfg.cpolar_authtoken
        elif provider_name == "cloudflare":'''

new_ts = '''        kwargs: dict = {"binary_path": cfg.binary_path}
        if provider_name == "cpolar":
            kwargs["authtoken"] = cfg.cpolar_authtoken
        elif provider_name == "tailscale":
            # 路径区分模式：path_prefix 非空时启用多应用路径前缀
            kwargs["path_prefix"] = cfg.path_prefix
        elif provider_name == "cloudflare":'''

assert edit_file(ts_file, old_ts, new_ts), "tunnel_service.py 失败"

print("\n=== tunnel_service.py 修改完成 ===")


# === 3. yaml_config.py: TunnelConfig 添加 path_prefix 字段 ===
yc_file = BASE + r'\src\xianyu_hunter\infra\yaml_config.py'

old_yc = '''    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False
    tunnel_mode: str = "quick"'''

new_yc = '''    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False
    # Tailscale 路径区分模式：非空时用 --set-path 注册路径前缀
    # 多应用同节点共存时各分配独立前缀（如 /xianyu/、/news/）
    path_prefix: str = "/xianyu/"
    tunnel_mode: str = "quick"'''

assert edit_file(yc_file, old_yc, new_yc), "yaml_config.py 失败"

print("\n=== yaml_config.py 修改完成 ===")
print("\n全部完成!")
