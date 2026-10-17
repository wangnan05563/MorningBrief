import json, collections

T = json.load(open('themes.json', encoding='utf-8'))
rows = [l.rstrip('\n').split('\t') for l in open('rows.tsv', encoding='utf-8')
        if len(l.rstrip('\n').split('\t')) >= 6]
R = {r[0]: r for r in rows}

# 批次 → 里程碑主归属
base = {}
for m, themes in {
    'M1': ['R3 脱敏值回写/不可逆数据毁损', 'R2 加载失败回落默认值后保存即覆写'],
    'M2': ['R7 高危动作缺确认或点了没反应'],
    'M3': ['R1 静默失败/错误被吞成空态或正常态'],
    'M4': ['R4 枚举/引导/文档与实现漂移', '前后端契约字段不匹配'],
    'M5': ['R5 统计口径与单位误读'],
    'M6': ['信息架构与导航（tabBar/孤儿页/重复职责）', '深链/状态持久化/跨端丢参'],
    'M7': ['R6 长任务/流式基本能力缺失', '其他高危'],
}.items():
    for t in themes:
        for i in T[t]:
            base[i] = m

# 评审后的人工归属修正（按内容语义）
MOVE = {
    'A12': 'M4',
    'A19': 'M3',
    'D78': 'M3',
    'E1': 'M3',
    'M54': 'M3',
    'J1': 'M6',
    'I27': 'M6',
    'J5': 'M6',
    'J14': 'M6',

    'D14': 'M2',            # 引导锚点，非配置覆写
    'C17': 'M7',            # 频道图标未序列化
    'C92': 'M4',            # 文案与实现不符
    'D56': 'M7',            # 筛选计数不刷新（R6 误归）
    'J27': 'M7',            # 缓冲态未呈现（R6 误归）
    'C68': 'M6', 'C80': 'M7', 'J21': 'M6', 'J29': 'M7',
    'J105': 'M6', 'J107': 'M7', 'J60': 'M6', 'J72': 'M6',
    'J77': 'M6', 'J80': 'M6', 'J98': 'M6', 'J99': 'M6',
    'D35': 'M5', 'D68': 'M5', 'G2': 'M1', 'G8': 'M1',
    'C15': 'M7', 'C18': 'M7', 'C27': 'M7', 'C37': 'M7',
    'C66': 'M4', 'J24': 'M6', 'J28': 'M7', 'J32': 'M7',
    'J45': 'M6', 'J46': 'M6', 'J48': 'M6', 'J59': 'M7',
    'J73': 'M7', 'J81': 'M7', 'I5': 'M7', 'I49': 'M7',
    'M78': 'M4', 'M95': 'M2', 'M16': 'M1',
}
base.update(MOVE)

assert len(base) == 142, len(base)
cnt = collections.Counter(base.values())
print(cnt)
for m in ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7']:
    ids = sorted([k for k, v in base.items() if v == m], key=lambda x: (x[0], int(x[1:])))
    print(f'\n### {m}（{len(ids)}）')
    print('、'.join(ids))
json.dump(base, open('id_to_milestone.json', 'w', encoding='utf-8'), ensure_ascii=False)
