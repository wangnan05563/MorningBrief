"""Karpathy wiki 改造脚本 part2：
1. TunnelService.start 中 configChanged 添加 pathPrefix 比较
2. types.ts 的 TunnelConfig 添加 pathPrefix 字段
3. config.ts defaultConfig() 添加 pathPrefix 默认值 /wiki/
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

TARGETS = {
    'tunnel_service': r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\tunnel\tunnel-service.ts",
    'types': r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\types.ts",
    'config': r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\config.ts",
}


def read_text(path: str) -> str:
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def write_text(path: str, text: str) -> None:
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    cnt = text.count(old)
    print(f"[{label}] occurrences: {cnt}")
    if cnt != 1:
        print(f"[{label}] PROBE_FAIL")
        print(f"  old[:200] = {old[:200]!r}")
        sys.exit(1)
    return text.replace(old, new)


def main() -> None:
    # === 1. tunnel-service.ts: TunnelService.start 添加 pathPrefix 比较 ===
    ts_path = TARGETS['tunnel_service']
    text = read_text(ts_path)
    print(f"tunnel-service.ts FileLength: {len(text)}")

    old_a = """      this.currentConfig.tunnelMode !== config.tunnelMode ||
      this.currentConfig.tunnelId !== config.tunnelId ||
      this.currentConfig.hostname !== config.hostname;"""
    new_a = """      this.currentConfig.tunnelMode !== config.tunnelMode ||
      this.currentConfig.tunnelId !== config.tunnelId ||
      this.currentConfig.hostname !== config.hostname ||
      this.currentConfig.pathPrefix !== config.pathPrefix;"""
    text = replace_once(text, old_a, new_a, "A: configChanged pathPrefix")
    write_text(ts_path, text)

    # === 2. types.ts: TunnelConfig 添加 pathPrefix 字段 ===
    types_path = TARGETS['types']
    text = read_text(types_path)
    print(f"types.ts FileLength: {len(text)}")

    # 注意 types.ts 是 GBK 编码（中文乱码显示），但用 utf-8 解码后中文部分会是乱码字符
    # 我们只在英文注释处添加，避免编码问题
    old_b = """export interface TunnelConfig {
  provider: 'cloudflare' | 'cpolar' | 'tailscale';
  localPort: number;
  cpolarAuthtoken: string;
  binaryPath: string;
  autoStart: boolean;"""
    new_b = """export interface TunnelConfig {
  provider: 'cloudflare' | 'cpolar' | 'tailscale';
  localPort: number;
  cpolarAuthtoken: string;
  binaryPath: string;
  autoStart: boolean;
  // Tailscale path prefix for multi-app coexistence (e.g. /wiki/).
  // Empty string = root path mode (legacy behavior).
  // When non-empty, funnel --set-path registers path prefix; Funnel auto-strips prefix before forwarding.
  pathPrefix: string;"""
    text = replace_once(text, old_b, new_b, "B: TunnelConfig.pathPrefix")
    write_text(types_path, text)

    # === 3. config.ts: defaultConfig() 添加 pathPrefix 默认值 ===
    config_path = TARGETS['config']
    text = read_text(config_path)
    print(f"config.ts FileLength: {len(text)}")

    old_c = """    tunnel: {
      provider: 'cloudflare',
      localPort: 0,
      cpolarAuthtoken: '',
      binaryPath: '',
      autoStart: false,
      // Named Tunnel 默认 quick 模式（开箱即用），named 需三步向导配置后自动切换
      tunnelMode: 'quick',
      tunnelName: '',
      tunnelId: '',
      credentialsFile: '',
      hostname: '',
      certFile: '',
    },"""
    new_c = """    tunnel: {
      provider: 'cloudflare',
      localPort: 0,
      cpolarAuthtoken: '',
      binaryPath: '',
      autoStart: false,
      // Tailscale path prefix: /wiki/ for multi-app coexistence on same ts.net host.
      // Empty string = root path mode (legacy behavior).
      pathPrefix: '/wiki/',
      // Named Tunnel 默认 quick 模式（开箱即用），named 需三步向导配置后自动切换
      tunnelMode: 'quick',
      tunnelName: '',
      tunnelId: '',
      credentialsFile: '',
      hostname: '',
      certFile: '',
    },"""
    text = replace_once(text, old_c, new_c, "C: defaultConfig.pathPrefix")
    write_text(config_path, text)

    print("DONE_PART2")


if __name__ == '__main__':
    main()
