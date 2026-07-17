# 宸ヤ綔绌洪棿娓呯悊澶嶇洏鍒嗘瀽锛?026-07-05 鏇存柊锛?
> 鍩轰簬瀵逛竴涓疄闄呴」鐩?5 杞伐浣滅┖闂存竻鐞嗚凯浠ｇ殑娣卞害澶嶇洏锛屾彁鐐奸€氱敤缁忛獙銆?>
> 绗簲杞鐩橈紙2026-07-05锛夋柊澧烇細PowerShell 璇硶闄烽槺銆佸悗鍙拌繘绋嬫寔缁垱寤烘枃浠躲€?> 寮傚父鏂囦欢鍚嶅鐞嗐€侀厤缃己澶辨椂鐨勬ā寮忔帹鏂瓑鍦烘櫙銆?
---

## 缁村害涓€锛氭垚鍔熸墽琛屼换鍔＄殑瀹屾暣姝ラ

### 1.1 鏁翠綋鑺傚

5 杞凯浠ｉ€愭鍙戠幇鏂伴棶棰橈紝璇佹槑杩欐槸涓€涓?*鍛ㄦ湡鎬х淮鎶や换鍔?*鑰岄潪涓€娆℃€ф竻鐞嗐€?
| 杞 | 璧峰鏂囦欢鏁?| 缁撴潫鏂囦欢鏁?| 瑙﹀彂鍥犵礌 |
|---|---|---|---|
| 绗竴杞?| ~50 | ~32 | 鐢ㄦ埛鍒濇璇锋眰娓呯悊 |
| 绗簩杞?| ~32 | 18 | 鍚姩鑴氭湰缁熶竴 |
| 绗笁杞?| 18 | 18锛堢‘璁ゆ棤鏂板锛?| 涓诲姩澶嶆煡 |
| 绗洓杞?| 32 | 14 | 鏈嶅姟杩愯涓寔缁骇鐢熻繍琛屼骇鐗?|
| 绗簲杞?| 119 | 15锛?4 鐧藉悕鍗?+ 1 寮傚父閲嶅缓锛?| 閰嶇疆椹卞姩绯荤粺鍖栨竻鐞嗭紝寮曞叆 6 闃舵闂幆 |

### 1.2 姣忚疆閫氱敤 6 姝ユ祦绋?
1. **渚﹀療闃舵锛圧econ锛?*锛氱敤 LS/Glob 鍒楀嚭鏍圭洰褰曘€佸瓙鐩綍鏂囦欢娓呭崟
2. **褰掔被闃舵锛圕lassify锛?*锛氬缓绔?鏍圭洰褰曞厑璁告竻鍗?妯″瀷
3. **褰卞搷璇勪及锛圛mpact锛?*锛氭鏌ユ湇鍔＄姸鎬侊紙PID + 绔彛锛夊喅瀹氭槸鍚﹀仠姝?4. **鎵ц闃舵锛圗xecute锛?*锛氭寜"鍒犻櫎/绉诲姩/淇濈暀"涓夋。澶勭悊
5. **楠岃瘉闃舵锛圴erify锛?*锛氶€氳繃瀵煎叆鏍稿績妯″潡纭鏈牬鍧忓簲鐢?6. **褰掓。闃舵锛圓rchive锛?*锛氭洿鏂拌鑼冩枃妗?+ 寮哄寲 .gitignore

### 1.3 鍏抽敭鎶€鏈偣

- **Get-FileHash 鍘婚噸**锛氬厛姣斿鍚屽悕鏂囦欢 hash 閬垮厤璇垹鍞竴鍓湰
- **鍋滄鏈嶅姟鍓嶇疆**锛氭湇鍔¤繍琛屼腑浼氭寔鏈夋枃浠跺彞鏌勫鑷村垹闄ゅけ璐ユ垨鐢熸垚鏂颁骇鐗?- **鎵归噺鍏堜簬绮剧粏**锛氬厛涓€娆℃€у垹闄ゆ槑鏄惧瀮鍦撅紝鍐嶅鐞嗚竟鐣屾儏鍐?- **瀵煎叆楠岃瘉鍏滃簳**锛歚import xianyu_hunter` 浣滀负鏈€渚垮疁鐨勫洖褰掓祴璇?- **鏂囨。鍚屾鏇存柊**锛氭瘡娆℃竻鐞嗛兘鍦?`directory-structure.md` 鐣欏彉鏇磋褰?
---

## 缁村害浜岋細浠诲姟鎵ц杩囩▼涓殑涓嶇‘瀹氭€т笌澶辫触鐐?
### 2.1 涓嶇‘瀹氱偣

| 涓嶇‘瀹氱偣 | 瑙﹀彂鍦烘櫙 | 澶勭疆 |
|---|---|---|
| 鏍圭洰褰曟煇鏂囦欢鏄惁璇ヤ繚鐣?| `.env` 鍚晱鎰熼厤缃?vs 璇懡鍚嶄负 `.env` 鐨勫瀮鍦?| 璇诲彇鍓嶅嚑琛屽垽鏂槸鍚︿负鐪熷疄鐜鍙橀噺 |
| 鏈嶅姟鏄惁鍦ㄨ繍琛?| 宸茬煡搴旂敤鍦ㄨ窇锛屼絾 PID 鏂囦欢鍙兘宸插け鏁?| 鍙岄獙璇侊細PID 鏂囦欢 + netstat 绔彛鐩戝惉 |
| 鏂囦欢鍒犻櫎鍚庢槸鍚﹀彲鎭㈠ | 鐢ㄦ埛鏈槑纭?娓呯悊"鏄惁鍏佽鍒犻櫎 | 浼樺厛 Move 鍒?scripts/锛屾棤娉曞綊绫诲啀 Delete |
| `.scannerwork/` 绛夊ぇ鐩綍 | 浣撶Н 6-16 MB锛屼絾鍒犻櫎浼氬奖鍝?IDE 缂撳瓨 | 鍒楀叆 gitignore锛屼笅娆¤嚜鍔ㄥ拷鐣?|

### 2.2 澶辫触鐐?
1. **閲嶅悕鏂囦欢琚鍒?*锛氭牴鐩綍涓?`docs/04-绯荤粺缁存姢/sonar-reports/` 涓嬫湁鍚屽悕 SonarQube 鎶ュ憡锛岀鍥涜疆鎵嶉€氳繃 Get-FileHash 姣斿鍙戠幇鍐椾綑銆?2. **鏈嶅姟杩愯涓寔缁骇鐢熸柊鍨冨溇**锛氭竻鐞嗗悗鏍圭洰褰曟枃浠舵暟浠?14 娑ㄥ埌 32锛屽洜涓烘湇鍔″湪璺戜笖鏃?.gitignore 鎷︽埅銆?3. **闈欓粯鍚姩.vbs 鎵句笉鍒?launcher**锛氱涓€杞皢 `闈欓粯鍚姩.vbs` 绉昏蛋锛屼絾鏍圭洰褰曞寘瑁呭櫒纭紪鐮佷簡鐩稿璺緞锛岃皟鐢ㄥけ璐ャ€?4. **`.pre-commit-config.yaml` 鎷︽埅瑙勫垯涓嶅叏**锛氱涓夎疆鎵嶈ˉ鍏?`sonar-results/` 瑙勫垯銆?5. **璇噸瀹氬悜浜х墿鍙嶅鍑虹幇**锛歚<project_name>`銆乣<project_name>frontend` 鏄?PowerShell `command > filename` 閿欒杈撳叆浜х敓鐨勶紝姣忔娓呯悊瀹岃繕浼氬啀鐢熴€?
### 2.3 椋庨櫓鎺у埗缁忛獙

- **姘镐笉澶ц妯℃壒閲忓垹闄?*锛氬厛鎵撳嵃娓呭崟 + 浜哄伐纭锛屽啀鎵ц
- **鍒犻櫎鍓嶅厛澶囦唤 hash 琛?*锛氭妸鎵€鏈?灏嗗垹"鏂囦欢鐨?path+hash+size 鍐欏叆 `cleanup-YYYYMMDD.log`
- **鏍稿績妯″潡瀵煎叆浣滀负鏈€鍚庝竴閬撻椄**锛氫换浣曟竻鐞嗗悗閮借窇 `python -c "import <core_module>"`
- **鏈嶅姟杩愯涓彧鍒犱笉閲嶈鐨?*锛氭湇鍔¤繍琛屾椂鍙垹闄ら噸瀹氬悜浜х墿鍜屾祴璇曡緭鍑猴紝绉诲姩/缁撴瀯鍙樻洿鍏堝仠鏈嶅姟

---

## 缁村害涓夛細鍙娊璞＄殑鍥哄畾娴佺▼涓庡垽鏂€昏緫

### 3.1 鍥哄畾 6 闃舵娴佺▼

```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Phase 1    鈹傗攢鈹€鈹€鈻垛攤  Phase 2    鈹傗攢鈹€鈹€鈻垛攤  Phase 3    鈹?鈹? Recon      鈹?   鈹? Classify   鈹?   鈹? Impact     鈹?鈹? 鎵弿       鈹?   鈹? 褰掔被       鈹?   鈹? 褰卞搷璇勪及   鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?       鈹?                                   鈹?       鈹?                                   鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Phase 6    鈹傗梹鈹€鈹€鈹€鈹? Phase 5    鈹傗梹鈹€鈹€鈹€鈹? Phase 4    鈹?鈹? Archive    鈹?   鈹? Verify     鈹?   鈹? Execute    鈹?鈹? 褰掓。       鈹?   鈹? 楠岃瘉       鈹?   鈹? 鎵ц       鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

### 3.2 鍙娊璞＄殑鍒ゆ柇閫昏緫

**鍒ゆ柇涓€锛氭枃浠舵槸鍚﹀睘浜?鍨冨溇"锛?*

```
鏂囦欢 X 鏄瀮鍦?鉄?  鈭?pattern 鈭?garbage_patterns: match(X.name, pattern)
  OR
  X.path == workspace_root AND X.ext 鈭?allowed_extensions
  OR
  X.path == workspace_root AND X.name 涓嶅湪 allowed_root_files 娓呭崟
```

**鍒ゆ柇浜岋細鏂囦欢鏄惁灞炰簬"鑴氭湰"锛?*

```
鏂囦欢 X 鏄剼鏈?鉄?  X.ext 鈭?{ .py, .ps1, .bat, .sh, .js, .vbs }
  AND
  X.path 涓嶆槸宸茬煡浠ｇ爜鐩綍锛坰rc/銆乫rontend/src/銆乼ests/锛?  AND
  X 涓嶆槸閰嶇疆/鏁版嵁鏂囦欢锛堟寜 content sniff 鎺掗櫎锛?```

**鍒ゆ柇涓夛細鏈嶅姟鏄惁鍦ㄨ繍琛岋紵**

```
鏈嶅姟鍦ㄨ繍琛?鉄?  鈭?pid_file 鈭?service_indicators.pid_files: exists(pid_file)
  OR
  鈭?port 鈭?service_indicators.ports: port_in_listen(port)
```

**鍒ゆ柇鍥涳細鎿嶄綔鏄惁瀹夊叏锛?*

```
鎿嶄綔 O 瀵规枃浠?X 瀹夊叏 鉄?  X 鍦?backup_log 涓瓨鍦?hash 璁板綍
  AND
  service_running == false
  AND
  (O == Delete) 鉄?X 鍦ㄥ瀮鍦?閲嶅畾鍚戜骇鐗╁悕鍗?  (O == Move) 鉄?鐩爣鐩綍瀛樺湪涓斿彲鍐?```

### 3.3 鍙弬鏁板寲鐨勯厤缃?
```yaml
# cleanup-config.yaml 绀轰緥
workspace:
  root: "."                    # 宸ヤ綔绌洪棿鏍癸紙鐩稿鎴栫粷瀵硅矾寰勶級
  script_dir: "scripts"        # 鑴氭湰闆嗕腑鐩綍
  docs_dir: "docs"             # 鏂囨。鐩綍

root_allowlist:
  extensions: [".md", ".yaml", ".yml", ".toml", ".txt", ".gitignore", ".env", ".example", ".properties"]
  files:                       # 鏄惧紡鍏佽鐨勬牴鐩綍鏂囦欢
    - "README.md"
    - "CHANGELOG.md"
    - "VERSIONING.md"
    - "Dockerfile"
    - "docker-compose.yml"
    - "pyproject.toml"
    - "requirements.txt"
    - ".gitignore"
    - ".dockerignore"
    - ".env.example"
    - ".pre-commit-config.yaml"

script_extensions: [".py", ".ps1", ".bat", ".sh", ".js", ".vbs"]

garbage_patterns:
  redirect_artifacts: ["/0", "/<project_name>", "/<project_name>frontend", "/_r.json"]
  tmp_suffixes: [".tmp", ".bak", ".orig", ".txtcd", ".s3358_lines.txt", ".tmp_diff.txt"]
  test_outputs: ["/pytest_output.txt", "/pytest_result.txt", "/test_result.txt", "/test_debug_output.txt"]
  cache_dirs: [".scannerwork/", ".pytest_cache/", "sonar-results/", ".ruff_cache/"]

service_indicators:
  pid_files: ["logs/web.pid", "logs/app.pid"]
  ports: [8000, 8080, 5000]
  process_names: ["python", "uvicorn", "node"]

verification:
  import_statements:
    - "import xianyu_hunter"
    - "from xianyu_hunter import config"
  command: ".venv/Scripts/python.exe -c 'import xianyu_hunter; from xianyu_hunter import config, container'"

archive:
  changelog_path: "docs/standards/directory-structure.md"
  gitignore_path: ".gitignore"
  precommit_path: ".pre-commit-config.yaml"

safety:
  require_stopped_service: true
  backup_log_format: "cleanup-{YYYYMMDD-HHmmss}.log"
  min_confidence_to_delete: 0.8
```

---

## 缁村害鍥涳細璇ユ祦绋嬪拰鍒ゆ柇閫昏緫鐨勯€傜敤鍦烘櫙涓庝笉閫傜敤鍦烘櫙

### 4.1 閫傜敤鍦烘櫙

| 鍦烘櫙 | 閫傜敤搴?| 澶囨敞 |
|---|---|---|
| 闀挎湡缁存姢鐨?Python/Node 椤圭洰 | 猸愨瓙猸愨瓙猸?| 榛樿閰嶇疆宸茶鐩栦富娴佹妧鏈爤 |
| 閲嶅畾鍚?璋冭瘯浜х敓鐨勬牴鐩綍姹℃煋 | 猸愨瓙猸愨瓙猸?| 鐩存帴濂楃敤 `garbage_patterns` |
| 鑴氭湰鏂囦欢鏁ｈ惤鍚勫瓙鐩綍 | 猸愨瓙猸愨瓙猸?| 鎸?`script_extensions` 闆嗕腑鍗冲彲 |
| 鏈嶅姟杩愯涓寔缁骇鐢熻繍琛屼骇鐗?| 猸愨瓙猸愨瓙 | 闇€鍏堝仠鏈嶅姟 |
| 鍛ㄦ湡鎬ч闃叉€х淮鎶?| 猸愨瓙猸愨瓙猸?| 寤鸿绾冲叆 CI 鎴栧懆缁存姢鑴氭湰 |
| 澶氭妧鏈爤娣峰悎椤圭洰 | 猸愨瓙猸愨瓙 | 璋冩暣 `root_allowlist.extensions` 鍗冲彲 |
| 鍚?Docker/Compose 閰嶇疆鐨勯」鐩?| 猸愨瓙猸愨瓙猸?| 宸插湪榛樿娓呭崟 |

### 4.2 涓嶉€傜敤鍦烘櫙

| 鍦烘櫙 | 涓嶉€傜敤鍘熷洜 | 鏇夸唬鏂规 |
|---|---|---|
| 鍏ㄦ柊绌轰粨搴?| 鏃犳牴鐩綍姹℃煋锛屾棤闇€娓呯悊 | 璺宠繃鏈?skill |
| Monorepo 鍗曚竴鍖呴」鐩?| 纭紪鐮佹牴鐩綍鍋囪浼氳鍒?| 鏀逛负 per-package 妯″紡 |
| 鍖呭惈澶ч噺浜岃繘鍒惰祫婧?| 鑴氭湰鎵╁睍鍚嶈鍒欎笉閫傜敤 | 澧炲姞 binary_extensions 瑙勫垯 |
| 鏈嶅姟涓嶈兘鍋滅殑 7脳24 涓氬姟 | Phase 3 褰卞搷璇勪及鐨?鍏堝仠鏈嶅姟"鍘熷垯鏃犳硶鎵ц | 鏀归€犱负"杞垹闄?妯″紡锛堥噸鍛藉悕鍔?.trash 鍚庣紑锛?|
| 鍥㈤槦瑙勬ā > 20 浜虹殑鍏叡浠撳簱 | 涓汉娓呯悊涔犳儻鍙兘涓庡叾浠栨垚鍛樺啿绐?| 鏀逛负 PR 娴佺▼鑰岄潪鏈湴娓呯悊 |
| macOS/Linux-only 椤圭洰 | 鑴氭湰鍩轰簬 PowerShell 璇硶 | 鎻愪緵 bash 鐗堟湰鎴栫敤璺ㄥ钩鍙板懡浠?|
| 澶у瀷鏋勫缓浜х墿锛圙B 绾у埆锛?| 璇垹鏋勫缓浜х墿浼氬鑷撮噸鏂版瀯寤?| 寮哄埗 require explicit confirmation |
| 鍙楃増鏈帶鍒朵繚鎶ょ殑鐩綍锛坴endor/銆乶ode_modules/锛?| 鐗╃悊鍒犻櫎浼氱牬鍧忓寘瀹屾暣鎬?| 浠呭仛 .gitignore 寮哄寲锛屼笉瀹為檯鍒犻櫎 |

### 4.3 杈圭晫涓庨檷绾х瓥鐣?
- **鏈嶅姟涓嶈兘鍋?*锛氳烦杩?Phase 4 涓殑 Move锛屼粎鍋?Delete锛堟寜 trash 妯″紡锛?- **閰嶇疆缂哄け**锛氬洖閫€鍒伴粯璁?`cleanup-config.example.yaml` 骞舵彁绀虹敤鎴疯鐩?- **鏍稿績妯″潡瀵煎叆澶辫触**锛氫腑姝㈠綊妗ｏ紙Phase 6锛夛紝鎻愮ず鐢ㄦ埛浜哄伐浠嬪叆
- **鏍圭洰褰曟枃浠舵暟 > 50**锛氬厛 dry-run锛堜粎鎵撳嵃璁″垝锛屼笉瀹為檯鎵ц锛?
---

## 浜斻€佺浜旇疆娓呯悊澶嶇洏锛?026-07-05锛?
### 5.1 鏈疆鐗硅壊

鏈疆棣栨閲囩敤 `workspace-cleanup` 鎶€鑳界殑瀹屾暣 6 闃舵闂幆娴佺▼锛?閰嶇疆椹卞姩 + hash 澶囦唤 + 楠岃瘉褰掓。锛屾槸鍘嗚疆涓渶瑙勮寖鐨勪竴娆°€?
**娓呯悊瑙勬ā锛?*
- 鏍圭洰褰曪細119 鈫?15 鏂囦欢锛堝垹闄?~118 涓級
- frontend锛?0 鈫?9 鏂囦欢锛堝垹闄?~21 涓級
- 缂撳瓨鐩綍锛? 涓紙`.scannerwork/` + `.pytest_cache/` + `sonar-results/`锛?- 閲婃斁绌洪棿锛殈42 MB

### 5.2 鏂板彂鐜扮殑涓嶇‘瀹氭€т笌澶辫触鐐?
#### 5.2.1 宸ュ叿灞傞檺鍒?
| 澶辫触鐐?| 瑙﹀彂鍦烘櫙 | 褰卞搷 | 瑙ｅ喅鏂规 |
|---|---|---|---|
| LS 杈撳嚭鎴柇 | 椤圭洰鏂囦欢鏁?> 40000 瀛楃闄愬埗 | 鏃犳硶鑾峰彇瀹屾暣鏂囦欢娓呭崟 | 鏀圭敤 PowerShell `Get-ChildItem -File` + 绱у噾鏍煎紡 |
| Glob `*.py` 鏃犺繑鍥?| 宸ュ叿琛屼负涓庨鏈熶笉绗?| 娴垂涓€杞帰娴?| 鐩存帴鐢?PowerShell 鍒楁枃浠讹紝涓嶄緷璧?Glob |

#### 5.2.2 PowerShell 璇硶闄烽槺锛堟柊澧烇級

| 闄烽槺 | 閿欒浠ｇ爜 | 閿欒淇℃伅 | 淇 |
|---|---|---|---|
| 椹卞姩鍣ㄥ紩鐢?| `"Port $port: not listening"` | `Variable reference is not valid. ':' was followed by a valid variable name` | 鏀圭敤 `${port}: not listening` |
| 鍝堝笇琛?strict mode | `$stats.Errors++` | `PropertyNotFound` | 鏀圭敤绠€鍗曞彉閲?`$script:errorCount++` |
| 寮傚父鏂囦欢鍚?| `Join-Path $root "not enabled*"` | 璺緞瑙ｆ瀽澶辫触 | 鐢?`Get-ChildItem + Where-Object` 鍖归厤 |

**缁忛獙鏁欒锛?* PowerShell 鍝堝笇琛ㄥ湪 strict mode 涓嬪睘鎬ч€掑浼氭姤閿欙紝
搴斾娇鐢?`[PSCustomObject]@{}` 鎴栫畝鍗曞彉閲忋€傛墍鏈?`$var:` 鍚庤窡闈炲彉閲忓悕瀛楃鐨勫満鏅?閮介渶鐢?`${var}` 鍖呰９銆?
#### 5.2.3 鏈嶅姟妫€娴嬬洸鍖猴紙鏂板锛?
| 鐩插尯 | 瀹為檯鍦烘櫙 | 妫€娴嬬粨鏋?| 淇 |
|---|---|---|---|
| PID 鏂囦欢缂哄け | 鏈嶅姟鍦ㄨ繍琛屼絾鏈啓 PID 鏂囦欢 | 璇垽涓?鏈嶅姟鏈繍琛? | 澧炲姞绔彛 + 杩涚▼鍚?+ 鏂囦欢鍗犵敤涓夐噸妫€娴?|
| 鏂囦欢琚崰鐢?| `run.stdout.log` 琚湇鍔℃寔鏈?| hash 璁＄畻澶辫触 | 鏂囦欢鍗犵敤浣滀负鏈嶅姟杩愯鐨勯棿鎺ヨ瘉鎹?|

**缁忛獙鏁欒锛?* PID 鏂囦欢涓嶅彲闈狅紙鍙兘缂哄け鎴栨畫鐣欙級锛屽繀椤诲閲嶈瘉鎹厹搴曘€?閰嶇疆涓柊澧?`file_occupancy_probes` 浣滀负绗洓閬撴娴嬨€?
#### 5.2.4 鍚庡彴杩涚▼鎸佺画鍒涘缓鏂囦欢锛堟柊澧烇級

**鐜拌薄锛?* 娓呯悊杩囩▼涓彂鐜版柊鏂囦欢琚寔缁垱寤猴細
- `compare_*.ps1` / `do_git_commit.ps1` / `integrate_*.ps1`锛坰kill 闆嗘垚鑴氭湰锛?- `ubprocess; r=subprocess.run([...])`锛圥owerShell 璇噸瀹氬悜浜х墿锛岃閲嶅缓 3 娆★級

**鍘熷洜锛?* 骞跺彂鐨?AI 浼氳瘽鎴栧悗鍙拌剼鏈湪鎵ц git diff 鎿嶄綔锛屼骇鐢熻閲嶅畾鍚戜骇鐗┿€?
**褰卞搷锛?* 娓呯悊"澶嶅彂"锛屾牴鐩綍鏂囦欢鏁版棤娉曠ǔ瀹氫笅闄嶃€?
**瑙ｅ喅鏂规锛?*
1. 鏂板 `stability_check` 閰嶇疆鍧楋紝鍒犻櫎鍚庣瓑寰?N 绉掑鎵?2. 鍖归厤 `recurrence_patterns` 鍒ゆ柇鏄惁涓哄凡鐭ュ悗鍙拌繘绋嬩骇鐗?3. 鎸?`recurrence_action`锛坵arn/stop/soft_delete锛夌瓥鐣ュ鐞?4. 瓒呰繃 `max_recurrence` 寮哄埗鍋滄锛屾彁绀虹敤鎴锋帓鏌ュ悗鍙拌繘绋?
#### 5.2.5 閰嶇疆瑕嗙洊鐩插尯锛堟柊澧烇級

**鐜拌薄锛?* example 閰嶇疆鏈鐩栦互涓嬫柊鍨嬭皟璇曚骇鐗╋細
- skill 闆嗘垚鑴氭湰锛坄compare_*.ps1` / `do_git_commit.ps1` 绛夛級
- git 璋冭瘯鑴氭湰锛坄git_menu_history.py` / `git_show_output.txt` 绛夛級
- 楠岃瘉鑴氭湰锛坄verify_*.py` / `verify_*.txt` 绛夛級

**瑙ｅ喅鏂规锛?*
1. 鎵╁睍 `garbage_patterns` 鏂板 `skill_debug_artifacts` 绫诲埆
2. 鏂板 `detection` 閰嶇疆鍧楋紝鏀寔鍩轰簬鏂囦欢鍚嶇壒寰佺殑妯″紡鎺ㄦ柇
3. 鎺ㄦ柇妯″紡鑷姩鍔犲叆 .gitignore 闃叉澶嶅彂

### 5.3 鏂板鐨勯檷绾х瓥鐣?
| 鍦烘櫙 | 闄嶇骇绛栫暐 | 閰嶇疆椤?|
|---|---|---|
| 閰嶇疆缂哄け | 鍥為€€鍒?example + 妯″紡鎺ㄦ柇 | `detection.enabled: true` |
| PID 鏂囦欢缂哄け | 绔彛 + 杩涚▼鍚?+ 鏂囦欢鍗犵敤涓夐噸妫€娴?| `service_indicators.file_occupancy_probes` |
| 鍚庡彴杩涚▼鎸佺画鍒涘缓鏂囦欢 | 绋冲畾鎬ф鏌?+ 澶嶅彂澶勭悊 | `stability_check.*` |
| 寮傚父鏂囦欢鍚?| Get-ChildItem + Where-Object 鍖归厤 | `safety.special_filename_handling: "safe"` |
| 鏈嶅姟涓嶈兘鍋?| 杞垹闄わ紙閲嶅懡鍚?.trash 鍚庣紑锛?| `safety.soft_delete_suffix` |
| 璺ㄥ钩鍙?| 閰嶇疆涓殑鍛戒护鍙樹綋 | `platform.commands.{windows/linux/macos}` |

### 5.4 绗簲杞竻鐞嗙殑鍏抽敭鎶€鏈偣

- **閰嶇疆椹卞姩绯荤粺鍖?*锛氭墍鏈夎鍒欓€氳繃 YAML 閰嶇疆绠＄悊锛岄浂纭紪鐮?- **hash 澶囦唤瀹屾暣鎬?*锛?25 涓枃浠?SHA256 澶囦唤鑷?`logs/cleanup-20260705-000340.log`
- **鏈嶅姟鍋滄鍓嶇疆**锛氭娴嬪埌绔彛 8000 鐩戝惉鍚庡仠姝㈡湇鍔★紙PID 33540锛?- **姣忔壒鍒犻櫎鍚庨獙璇?*锛氬強鏃跺彂鐜板垹闄よ剼鏈け鏁堥棶棰?- **妯″紡鎺ㄦ柇鍏滃簳**锛氳瘑鍒厤缃湭瑕嗙洊鐨勬柊鍨嬭皟璇曚骇鐗?- **绋冲畾鎬ф鏌?*锛氬彂鐜板悗鍙拌繘绋嬫寔缁垱寤烘枃浠剁殑闂
- **褰掓。涓変欢濂?*锛?gitignore + .pre-commit + changelog 鍚屾鏇存柊

### 5.5 閫傜敤鍦烘櫙鏇存柊

#### 鏂板涓嶉€傜敤鍦烘櫙

| 鍦烘櫙 | 涓嶉€傜敤鍘熷洜 | 鏇夸唬鏂规 |
|---|---|---|
| 鏈夊苟鍙?AI 浼氳瘽鐨勯」鐩?| 鍚庡彴杩涚▼鎸佺画鍒涘缓鏂囦欢锛屾竻鐞?澶嶅彂" | 鍏堟帓鏌ュ苟鍋滄鎵€鏈夊悗鍙颁細璇濓紝鍐嶆墽琛屾竻鐞?|
| 閰嶇疆鏈鐩栫殑鏂板瀷璋冭瘯浜х墿 | garbage_patterns 鏃犳硶绌蜂妇鎵€鏈夋ā寮?| 鍚敤 `detection` 妯″紡鎺ㄦ柇 |
| 鏂囦欢鍚嶅惈鐗规畩瀛楃鐨勮閲嶅畾鍚戜骇鐗?| 鐩存帴璺緞瀛楃涓插け璐?| 浣跨敤 `safe` 妯″紡锛圙et-ChildItem 鍖归厤锛?|

#### 鏂板寮哄寲閫傜敤鍦烘櫙

| 鍦烘櫙 | 寮哄寲鑳藉姏 | 閰嶇疆椤?|
|---|---|---|
| 鏈嶅姟杩愯浣嗘棤 PID 鏂囦欢 | 鏂囦欢鍗犵敤鎺㈡祴鍏滃簳 | `file_occupancy_probes` |
| 璺ㄥ钩鍙伴」鐩?| 閰嶇疆涓殑鍛戒护鍙樹綋 | `platform.commands.*` |
| 鏂板瀷璋冭瘯浜х墿 | 妯″紡鎺ㄦ柇 + 鑷姩鍔犲叆 .gitignore | `detection.*` |

---

## 六、PowerShell 最佳实践

> 本节内容与 [decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) Section 6 完全重复，请查阅 decisions.md 获取完整代码示例。

**要点回顾：** 变量引用陷阱（${var}）、哈希表 strict mode（[PSCustomObject]）、异常文件名（Get-ChildItem | Where-Object）、文件占用检测（[System.IO.File]::Open()）、跨平台命令选择（platform.commands）。

---

## 七、配置降级策略

> 本节内容与 [decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) Section 7 完全重复，请查阅 decisions.md 获取完整表格。

**要点回顾：** 加载优先级（用户配置 > 示例 > STOP）、不完整配置的降级策略、模式推断置信度阈值（1.0/0.9/0.8/0.7/<0.7）。推断模式是配置缺失时的兜底，不能替代完整配置。

