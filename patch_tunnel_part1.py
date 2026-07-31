"""Karpathy wiki tunnel-service.ts 改造脚本：TailscaleProvider 路径前缀支持。

参考 20_News/backend/app/services/tunnel_providers.py 实现，TypeScript 版需做：
1. 类构造函数添加 pathPrefix 参数（默认空串）
2. 添加 _normalizePathPrefix 静态方法
3. funnel 命令构造时添加 --set-path
4. publicUrl 构造时包含 pathPrefix
5. stop 方法路径模式不调用 funnel off
6. refreshStatus 检查 Handlers 中是否存在自己的路径前缀
7. createProvider 工厂函数传递 pathPrefix
"""
import io
import sys
import os

# 强制 stdout 用 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

TARGET = r"D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\tunnel\tunnel-service.ts"


def read_text(path: str) -> str:
    with open(path, 'rb') as f:
        data = f.read()
    # 用 utf-8 解码（文件原编码）
    return data.decode('utf-8')


def write_text(path: str, text: str) -> None:
    # 写回 UTF-8 无 BOM
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    cnt = text.count(old)
    print(f"[{label}] occurrences: {cnt}")
    if cnt != 1:
        print(f"[{label}] PROBE_FAIL")
        # 输出 old 的前 100 字符方便定位
        print(f"  old[:100] = {old[:100]!r}")
        sys.exit(1)
    return text.replace(old, new)


def main() -> None:
    text = read_text(TARGET)
    print(f"FileLength: {len(text)}")

    # === 替换 1: 类定义添加 pathPrefix 字段 + 构造函数 + _normalizePathPrefix 静态方法 ===
    old1 = """class TailscaleProvider extends TunnelProvider {
  private detectedBinary: string | null = null;
  // status 缓存：getter 同步返回，后台异步刷新避免 execFileSync 阻塞事件循环
  private cachedStatus: 'running' | 'stopped' = 'stopped';
  private statusTimer: NodeJS.Timeout | null = null;

  binaryName(): string {
    return 'tailscale.exe';
  }"""
    new1 = """class TailscaleProvider extends TunnelProvider {
  private detectedBinary: string | null = null;
  // status 缓存：getter 同步返回，后台异步刷新避免 execFileSync 阻塞事件循环
  private cachedStatus: 'running' | 'stopped' = 'stopped';
  private statusTimer: NodeJS.Timeout | null = null;
  // 路径前缀（规范化后 /xxx/ 形式，空串表示根路径模式-旧行为）
  private readonly pathPrefix: string;

  constructor(localPort: number, binaryPath: string, pathPrefix: string = '') {
    super(localPort, binaryPath);
    this.pathPrefix = TailscaleProvider._normalizePathPrefix(pathPrefix);
  }

  // 规范化路径前缀为 /xxx/ 形式，空字符串表示根路径模式（保持旧行为）
  // 为什么单独静态方法：构造函数和外部调用都需复用同一规范化逻辑
  private static _normalizePathPrefix(prefix: string): string {
    if (!prefix) return '';
    let p = prefix.trim();
    if (!p.startsWith('/')) p = '/' + p;
    if (!p.endsWith('/')) p = p + '/';
    return p;
  }

  binaryName(): string {
    return 'tailscale.exe';
  }"""
    text = replace_once(text, old1, new1, "R1: class def + ctor")

    # === 替换 2: funnel 命令构造（添加 --set-path）===
    old2 = """    const binary = this.detectedBinary!;
    const args = ['funnel', '--bg', '--yes', `http://127.0.0.1:${this.localPort}`];"""
    new2 = """    const binary = this.detectedBinary!;
    // 构造 funnel 命令：路径区分模式用 --set-path，根路径模式用默认行为
    // --set-path 是追加模式，不会覆盖其他应用的路径配置，实现多应用共存
    const args = ['funnel', '--bg', '--yes'];
    if (this.pathPrefix) {
      args.push('--set-path', this.pathPrefix);
    }
    args.push(`http://127.0.0.1:${this.localPort}`);"""
    text = replace_once(text, old2, new2, "R2: funnel args")

    # === 替换 3: waitForTailscaleFunnel 中的成功标志 publicUrl 构造 ===
    old3 = """        // 检测成功标志
        if (/Funnel started|listening on/i.test(text)) {
          this.publicUrl = `https://${dnsName}`;
          cleanup();
          resolve();
          return;
        }"""
    new3 = """        // 检测成功标志
        if (/Funnel started|listening on/i.test(text)) {
          this.publicUrl = `https://${dnsName}${this.pathPrefix}`;
          cleanup();
          resolve();
          return;
        }"""
    text = replace_once(text, old3, new3, "R3: success publicUrl")

    # === 替换 4: onExit 中的 publicUrl 构造 ===
    old4 = """      const onExit = (code: number | null): void => {
        cleanup();
        if (code === 0) {
          // 进程退出码 0 可能是配置成功后正常退出
          this.publicUrl = `https://${dnsName}`;
          resolve();
        } else {"""
    new4 = """      const onExit = (code: number | null): void => {
        cleanup();
        if (code === 0) {
          // 进程退出码 0 可能是配置成功后正常退出
          this.publicUrl = `https://${dnsName}${this.pathPrefix}`;
          resolve();
        } else {"""
    text = replace_once(text, old4, new4, "R4: onExit publicUrl")

    # === 替换 5: stop 方法（路径模式不调用 funnel off）===
    old5 = """  // 覆写 stop：异步执行 tailscale funnel off，不等待结果避免阻塞事件循环
  // 为什么用 spawn fire-and-forget：stop 在 SIGINT 钩子中调用，阻塞会导致退出延迟
  stop(): void {
    if (this.detectedBinary) {
      // unref() 让子进程不阻止 Node.js 退出
      spawn(this.detectedBinary, ['funnel', 'off'], {
        windowsHide: true,
        stdio: 'ignore',
      }).unref();
    }
    // 清除状态刷新定时器
    if (this.statusTimer) {
      clearInterval(this.statusTimer);
      this.statusTimer = null;
    }
    this.cachedStatus = 'stopped';
    this.detectedBinary = null;
    this.publicUrl = null;
    this.exited = true;
  }"""
    new5 = """  // 覆写 stop：路径模式下不调用 funnel off（避免关闭其他应用的 Funnel 路径）
  // 根路径模式（旧行为）：异步执行 tailscale funnel off，不等待结果避免阻塞事件循环
  // 为什么用 spawn fire-and-forget：stop 在 SIGINT 钩子中调用，阻塞会导致退出延迟
  stop(): void {
    if (this.pathPrefix) {
      // 路径区分模式：Tailscale 无移除单个路径的命令，停止后路径配置保留
      // 重新启动应用后 --set-path 幂等更新配置自动恢复
      if (this.statusTimer) {
        clearInterval(this.statusTimer);
        this.statusTimer = null;
      }
      this.cachedStatus = 'stopped';
      this.publicUrl = null;
      this.exited = true;
      return;
    }
    if (this.detectedBinary) {
      // unref() 让子进程不阻止 Node.js 退出
      spawn(this.detectedBinary, ['funnel', 'off'], {
        windowsHide: true,
        stdio: 'ignore',
      }).unref();
    }
    // 清除状态刷新定时器
    if (this.statusTimer) {
      clearInterval(this.statusTimer);
      this.statusTimer = null;
    }
    this.cachedStatus = 'stopped';
    this.detectedBinary = null;
    this.publicUrl = null;
    this.exited = true;
  }"""
    text = replace_once(text, old5, new5, "R5: stop method")

    # === 替换 6: refreshStatus 方法（检查 Handlers 中路径前缀）===
    old6 = """  // 异步刷新 status 缓存：用 execAsync 非阻塞查询 funnel status --json
  private async refreshStatus(): Promise<void> {
    if (!this.detectedBinary) {
      this.cachedStatus = 'stopped';
      return;
    }
    try {
      const result = await this.runCliAsync(['funnel', 'status', '--json']);
      const data = JSON.parse(result) as Record<string, unknown>;
      const allowFunnel = data.AllowFunnel as Record<string, boolean> | undefined;
      if (!allowFunnel) {
        this.cachedStatus = 'stopped';
        return;
      }
      for (const [endpoint, enabled] of Object.entries(allowFunnel)) {
        if (!enabled) continue;
        const host = endpoint.split(':')[0].replace(/\\.$/, '');
        if (host.toLowerCase().endsWith('.ts.net')) {
          this.publicUrl = `https://${host}`;
          this.cachedStatus = 'running';
          return;
        }
      }
      this.cachedStatus = 'stopped';
    } catch {
      this.publicUrl = null;
      this.cachedStatus = 'stopped';
    }
  }"""
    new6 = """  // 异步刷新 status 缓存：用 execAsync 非阻塞查询 funnel status --json
  // 路径区分模式：通过检查 Handlers 中是否存在自己的路径前缀确认当前应用 Funnel 配置
  private async refreshStatus(): Promise<void> {
    if (!this.detectedBinary) {
      this.cachedStatus = 'stopped';
      return;
    }
    try {
      const result = await this.runCliAsync(['funnel', 'status', '--json']);
      const data = JSON.parse(result) as Record<string, unknown>;
      const allowFunnel = data.AllowFunnel as Record<string, boolean> | undefined;
      if (!allowFunnel) {
        this.cachedStatus = 'stopped';
        return;
      }
      let host: string | null = null;
      for (const [endpoint, enabled] of Object.entries(allowFunnel)) {
        if (!enabled) continue;
        const h = endpoint.split(':')[0].replace(/\\.$/, '');
        if (h.toLowerCase().endsWith('.ts.net')) {
          host = h;
          break;
        }
      }
      if (!host) {
        this.cachedStatus = 'stopped';
        return;
      }
      // 路径区分模式：检查 Handlers 中是否存在自己的路径前缀
      if (this.pathPrefix) {
        const web = data.Web as Record<string, unknown> | undefined;
        let handlers: Record<string, unknown> | undefined;
        if (web && typeof web === 'object') {
          for (const cfg of Object.values(web)) {
            if (cfg && typeof cfg === 'object' && 'Handlers' in (cfg as Record<string, unknown>)) {
              handlers = (cfg as Record<string, unknown>).Handlers as Record<string, unknown>;
              break;
            }
          }
        }
        if (!handlers || !(this.pathPrefix in handlers)) {
          this.cachedStatus = 'stopped';
          return;
        }
        this.publicUrl = `https://${host}${this.pathPrefix}`;
        this.cachedStatus = 'running';
        return;
      }
      // 根路径模式（旧行为）：URL 不含路径前缀
      this.publicUrl = `https://${host}`;
      this.cachedStatus = 'running';
    } catch {
      this.publicUrl = null;
      this.cachedStatus = 'stopped';
    }
  }"""
    text = replace_once(text, old6, new6, "R6: refreshStatus")

    # === 替换 7: createProvider 工厂函数传递 pathPrefix ===
    old7 = """    case 'tailscale':
      return new TailscaleProvider(localPort, config.binaryPath);"""
    new7 = """    case 'tailscale':
      return new TailscaleProvider(localPort, config.binaryPath, config.pathPrefix);"""
    text = replace_once(text, old7, new7, "R7: createProvider")

    write_text(TARGET, text)
    print("DONE_PART1")


if __name__ == '__main__':
    main()
