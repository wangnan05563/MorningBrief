/**
 * 统计指标单位元数据夹具（FR-UX-501 / T02506）。
 *
 * 内容不是手抄的：由 `python scripts/gen_stats_metric_meta.py` 从后端唯一真源
 * `backend/app/services/stats_metrics.py` 生成到同目录 stats-metric-meta.json，
 * `backend/tests/test_stats_metric_meta.py` 会校验两者一致。
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const FILE = join(dirname(fileURLToPath(import.meta.url)), 'stats-metric-meta.json')

export const statsMetricMeta = JSON.parse(readFileSync(FILE, 'utf-8'))
