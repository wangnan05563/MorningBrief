; MorningBrief 安装包脚本
; 由 build-exe.ps1 自动调用：iscc /DMyAppVersion=<version> installer.iss
; 产物：release/MorningBrief-Setup-v<version>.exe
;
; 版本号通过命令行参数 /DMyAppVersion 传入（build-exe.ps1 从配置读取）
; 手动编译：iscc /DMyAppVersion=1.2.0 installer.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0.0"
#endif

[Setup]
AppName=MorningBrief
AppVersion={#MyAppVersion}
AppPublisher=MorningBrief
DefaultDirName={autopf}\MorningBrief
DefaultGroupName=MorningBrief
; 复用产品图标（assets\MorningBrief.ico，与 exe 同源），避免安装包显示 Inno 默认图标
; 注：这里不用 #if exist() 判断——Inno Setup ISPP 中的 exist() 是 Pascal 脚本内置函数，
;     在 [Setup] 阶段的 #if 预处理里无法直接用，会报 "Undeclared identifier: exist"。
;     若图标缺失（首次克隆仓库还没生成），手动注释下行即可回退到 Inno 默认图标。
SetupIconFile=release\assets\MorningBrief.ico
UninstallDisplayIcon={app}\MorningBrief.exe
OutputDir=release
OutputBaseFilename=MorningBrief-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; 仅支持 64 位系统（PyInstaller 产物为 x64）
; 使用 x64compatible 替代已弃用的 x64 标识符（Inno Setup 6.3+）
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 安装到 Program Files 需要管理员权限
PrivilegesRequired=admin
; 跳过"选择开始菜单文件夹"页面（使用默认值）
DisableProgramGroupPage=yes


[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[InstallDelete]
; 升级安装：先整目录删除旧前端产物，再复制新版本。
; 原因（T00775 实测）：apps/admin-web/dist/assets 里的 chunk 按内容哈希命名，
; 只做覆盖式复制时，新版本中已被移除的 chunk 会一直残留在安装目录——实测安装目录里
; 同时存在 9/18 与 9/20 两批 MaterialLibrary-*.js。一旦浏览器仍缓存旧 index.html，
; 就会静默加载旧版页面（表现为「代码已修但页面上看不到」）。
; admin-web 目录只放前端静态资源，无用户数据，可安全删除。
Type: filesandordirs; Name: "{app}\admin-web"

[Files]
; 整个 release\MorningBrief\ 目录打包进安装包
; 注意：.env 必须随包分发！release\MorningBrief\.env 由 build-exe.ps1 从 backend\.env
;       复制并适配而来，已包含真实密钥（WX_APPID/WX_SECRET 等）。若排除 .env，
;       安装后 exe 同级无 .env，WX_APPID 落空，导致小程序微信登录报 "appid missing"。
;       排除项仅保留：*.log（日志）、data\*（运行时自动生成的 SQLite 库）、logs\*。
Source: "release\MorningBrief\*"; DestDir: "{app}"; Excludes: "*.log,data\*,logs\*"; Flags: ignoreversion recursesubdirs createallsubdirs
; 显式包含 .env，确保即使被文件系统标记为隐藏属性也能进入安装包
Source: "release\MorningBrief\.env"; DestDir: "{app}"; Flags: ignoreversion
; 显式包含频道预制封面/图标（T00731）：data\* 已在上面被整体排除，
; 若不单独列出，全新安装的实例 data\channel_assets 为空，12 个频道封面全部 404。
; Flags=onlyifdoesntexist：只补缺失、不覆盖已有文件（用户可能替换过同名资产）；
; 升级场景下缺失的文件由后端启动时的 _seed_default_channel_assets 从随包副本补齐。
Source: "release\MorningBrief\data\channel_assets\*"; DestDir: "{app}\data\channel_assets"; Flags: onlyifdoesntexist

[Dirs]
; 预创建运行时目录（用户首次启动前就绪）
Name: "{app}\data"; Flags: uninsneveruninstall
Name: "{app}\data\channel_assets"; Flags: uninsneveruninstall
Name: "{app}\logs"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\MorningBrief"; Filename: "{app}\MorningBrief.exe"
Name: "{group}\卸载 MorningBrief"; Filename: "{uninstallexe}"
Name: "{commondesktop}\MorningBrief"; Filename: "{app}\MorningBrief.exe"; Tasks: desktopicon

[Run]
; 安装完成后可选启动
Filename: "{app}\MorningBrief.exe"; Description: "立即启动 MorningBrief"; Flags: nowait postinstall skipifsilent
