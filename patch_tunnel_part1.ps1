$target = "D:\code\otherProjects\19_Karpathy-AI+Obsidian知识库\karpathy-wiki\api\src\tunnel\tunnel-service.ts"
$bytes = [System.IO.File]::ReadAllBytes($target)
$text = [System.Text.Encoding]::UTF8.GetString($bytes)

# === 替换 1: 类定义添加 pathPrefix 字段 + 构造函数 + _normalizePathPrefix 静态方法 ===
$old1 = @'
class TailscaleProvider extends TunnelProvider {
  private detectedBinary: string | null = null;
  // status 缓存：getter 同步返回，后台异步刷新避免 execFileSync 阻塞事件循环
  private cachedStatus: 'running' | 'stopped' = 'stopped';
  private statusTimer: NodeJS.Timeout | null = null;

  binaryName(): string {
    return 'tailscale.exe';
  }
'@
$new1 = @'
class TailscaleProvider extends TunnelProvider {
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
  }
'@
$count1 = ([regex]::Matches($text, [regex]::Escape($old1))).Count
Write-Host "Replace1 count: $count1"
if ($count1 -ne 1) { Write-Host "PROBE1_FAIL"; exit 1 }
$text = $text.Replace($old1, $new1)

# === 替换 2: funnel 命令构造（添加 --set-path）===
$old2 = @'
    const binary = this.detectedBinary!;
    const args = ['funnel', '--bg', '--yes', `http://127.0.0.1:${this.localPort}`];
'@
$new2 = @'
    const binary = this.detectedBinary!;
    // 构造 funnel 命令：路径区分模式用 --set-path，根路径模式用默认行为
    // --set-path 是追加模式，不会覆盖其他应用的路径配置，实现多应用共存
    const args = ['funnel', '--bg', '--yes'];
    if (this.pathPrefix) {
      args.push('--set-path', this.pathPrefix);
    }
    args.push(`http://127.0.0.1:${this.localPort}`);
'@
$count2 = ([regex]::Matches($text, [regex]::Escape($old2))).Count
Write-Host "Replace2 count: $count2"
if ($count2 -ne 1) { Write-Host "PROBE2_FAIL"; exit 1 }
$text = $text.Replace($old2, $new2)

# === 替换 3: waitForTailscaleFunnel 中的成功标志 publicUrl 构造 ===
$old3 = @'
        // 检测成功标志
        if (/Funnel started|listening on/i.test(text)) {
          this.publicUrl = `https://${dnsName}`;
          cleanup();
          resolve();
          return;
        }
'@
$new3 = @'
        // 检测成功标志
        if (/Funnel started|listening on/i.test(text)) {
          this.publicUrl = `https://${dnsName}${this.pathPrefix}`;
          cleanup();
          resolve();
          return;
        }
'@
$count3 = ([regex]::Matches($text, [regex]::Escape($old3))).Count
Write-Host "Replace3 count: $count3"
if ($count3 -ne 1) { Write-Host "PROBE3_FAIL"; exit 1 }
$text = $text.Replace($old3, $new3)

# === 替换 4: onExit 中的 publicUrl 构造 ===
$old4 = @'
      const onExit = (code: number | null): void => {
        cleanup();
        if (code === 0) {
          // 进程退出码 0 可能是配置成功后正常退出
          this.publicUrl = `https://${dnsName}`;
          resolve();
        } else {
'@
$new4 = @'
      const onExit = (code: number | null): void => {
        cleanup();
        if (code === 0) {
          // 进程退出码 0 可能是配置成功后正常退出
          this.publicUrl = `https://${dnsName}${this.pathPrefix}`;
          resolve();
        } else {
'@
$count4 = ([regex]::Matches($text, [regex]::Escape($old4))).Count
Write-Host "Replace4 count: $count4"
if ($count4 -ne 1) { Write-Host "PROBE4_FAIL"; exit 1 }
$text = $text.Replace($old4, $new4)

# 写回文件（UTF-8 无 BOM）
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($target, $text, $utf8NoBom)
Write-Host "DONE_PART1"
