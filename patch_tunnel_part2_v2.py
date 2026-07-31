"""Karpathy wiki 改造脚本 part2 v2：
通用文件修改工具：自动检测 UTF-8/UTF-8-SIG 编码 + CRLF/LF 换行符，修改后保留原格式。

修改内容：
1. types.ts: TunnelConfig 添加 pathPrefix 字段
2. config.ts: defaultConfig() 添加 pathPrefix 默认值 /wiki/
（tunnel-service.ts 的 configChanged 已在 part1 之后的临时脚本中修改完成）
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

PATHS = {
    'types': r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\types.ts",
    'config': r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\config.ts",
}


def read_with_format(path: str):
    """读取文件并保留编码与换行符信息。

    返回 (text_without_bom, has_bom, newline)：
      - text_without_bom: 解码后的字符串（CRLF 已转为 LF，便于处理）
      - has_bom: 是否有 UTF-8 BOM
      - newline: 'crlf' 或 'lf'
    """
    with open(path, 'rb') as f:
        raw = f.read()
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    if has_bom:
        raw = raw[3:]
    # 统一用 utf-8 解码（无 BOM 后）
    text = raw.decode('utf-8')
    has_crlf = '\r\n' in text
    if has_crlf:
        text = text.replace('\r\n', '\n')
    return text, has_bom, ('crlf' if has_crlf else 'lf')


def write_with_format(path: str, text: str, has_bom: bool, newline: str) -> None:
    """按原编码与换行符写回文件。"""
    if newline == 'crlf':
        text = text.replace('\n', '\r\n')
    data = text.encode('utf-8')
    if has_bom:
        data = b'\xef\xbb\xbf' + data
    with open(path, 'wb') as f:
        f.write(data)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    cnt = text.count(old)
    print(f"[{label}] occurrences: {cnt}")
    if cnt != 1:
        print(f"[{label}] PROBE_FAIL")
        print(f"  old[:200] = {old[:200]!r}")
        sys.exit(1)
    return text.replace(old, new)


def main() -> None:
    # === 1. types.ts: TunnelConfig 添加 pathPrefix 字段 ===
    types_path = PATHS['types']
    text, has_bom, nl = read_with_format(types_path)
    print(f"types.ts: has_bom={has_bom}, newline={nl}, len={len(text)}")

    # TunnelConfig 接口定义部分（注释里中文是乱码也无妨，匹配英文部分即可）
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
    write_with_format(types_path, text, has_bom, nl)

    # === 2. config.ts: defaultConfig() 添加 pathPrefix 默认值 ===
    config_path = PATHS['config']
    text, has_bom, nl = read_with_format(config_path)
    print(f"config.ts: has_bom={has_bom}, newline={nl}, len={len(text)}")

    old_c = """    tunnel: {
      provider: 'cloudflare',
      localPort: 0,
      cpolarAuthtoken: '',
      binaryPath: '',
      autoStart: false,
      // Named Tunnel"""
    # 注意：config.ts 注释中可能含中文，这里只取前缀避免编码问题
    # 先精确匹配英文部分
    new_c = """    tunnel: {
      provider: 'cloudflare',
      localPort: 0,
      cpolarAuthtoken: '',
      binaryPath: '',
      autoStart: false,
      // Tailscale path prefix: /wiki/ for multi-app coexistence on same ts.net host.
      // Empty string = root path mode (legacy behavior).
      pathPrefix: '/wiki/',
      // Named Tunnel"""
    # 精确匹配（注意 config.ts 中的中文注释 - 用 UTF-8 解码后是正常中文）
    text = replace_once(text, old_c, new_c, "C: defaultConfig.pathPrefix")
    write_with_format(config_path, text, has_bom, nl)

    print("DONE_PART2")


if __name__ == '__main__':
    main()
