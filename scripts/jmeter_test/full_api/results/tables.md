# 性能数据表（自动生成）

## 各轮次总览

| 运行 | 样本 | RPS | Avg | P90 | P95 | P99 | Max | 错误率 | 真实缺陷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_admin | 360 | 20.8 | 47.6 | 35.0 | 125.0 | 731.0 | 6566 | 0.00% | 0 |
| baseline_c | 90 | 73.3 | 13.1 | 22.0 | 29.0 | 140.0 | 140 | 0.00% | 0 |
| soak_admin | 207371 | 14.4 | 277.2 | 463.0 | 614.0 | 1137.0 | 7910 | 0.00% | 0 |
| soak_c | 1747296 | 121.3 | 164.4 | 323.0 | 564.0 | 1394.0 | 14118 | 0.00% | 0 |
| stress_admin_read_10 | 11197 | 124.6 | 74.2 | 142.0 | 165.0 | 208.0 | 300 | 0.00% | 0 |
| stress_admin_read_25 | 11448 | 127.4 | 180.8 | 364.0 | 428.0 | 629.0 | 2828 | 0.00% | 0 |
| stress_admin_read_50 | 10938 | 121.7 | 378.5 | 754.0 | 895.0 | 2045.0 | 4229 | 0.00% | 0 |
| stress_c_read_10 | 24915 | 277.4 | 33.3 | 63.0 | 80.0 | 183.0 | 3317 | 0.00% | 0 |
| stress_c_read_100 | 23495 | 261.1 | 352.3 | 741.0 | 909.0 | 1260.0 | 1925 | 0.00% | 0 |
| stress_c_read_200 | 24972 | 276.3 | 663.4 | 1379.0 | 1634.0 | 2217.0 | 3927 | 0.00% | 0 |
| stress_c_read_50 | 24581 | 273.6 | 168.1 | 322.0 | 380.0 | 569.0 | 5255 | 0.00% | 0 |
| stress_c_write_10 | 10469 | 116.5 | 79.4 | 181.0 | 212.0 | 300.0 | 600 | 0.01% | 1 |
| stress_c_write_25 | 11143 | 124.0 | 186.0 | 440.0 | 489.0 | 595.0 | 812 | 0.02% | 2 |
| stress_c_write_50 | 11302 | 125.7 | 366.6 | 820.0 | 890.0 | 1114.0 | 1524 | 0.00% | 0 |

## 阶梯压测与拐点


### C 端读（拐点：吞吐饱和（增幅 <15% 且 P95 上升 >50%） @ 50 线程；峰值 277.4 RPS @ 10 线程）

| 线程 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 277.4 | 33.3 | 80.0 | 183.0 | 0.00% | 0 |
| 50 | 273.6 | 168.1 | 380.0 | 569.0 | 0.00% | 0 |
| 100 | 261.1 | 352.3 | 909.0 | 1260.0 | 0.00% | 0 |
| 200 | 276.3 | 663.4 | 1634.0 | 2217.0 | 0.00% | 0 |

### C 端写（拐点：出现 5xx/连接失败 @ 10 线程；峰值 125.7 RPS @ 50 线程）

| 线程 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 116.5 | 79.4 | 212.0 | 300.0 | 0.01% | 1 |
| 25 | 124.0 | 186.0 | 489.0 | 595.0 | 0.02% | 2 |
| 50 | 125.7 | 366.6 | 890.0 | 1114.0 | 0.00% | 0 |

### 管理端读（拐点：吞吐饱和（增幅 <15% 且 P95 上升 >50%） @ 25 线程；峰值 127.4 RPS @ 25 线程）

| 线程 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 124.6 | 74.2 | 165.0 | 208.0 | 0.00% | 0 |
| 25 | 127.4 | 180.8 | 428.0 | 629.0 | 0.00% | 0 |
| 50 | 121.7 | 378.5 | 895.0 | 2045.0 | 0.00% | 0 |

## 稳定性 soak_c（30 分钟窗口）

| 窗口 | 起始分钟 | 样本 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 215966 | 120.0 | 164.1 | 550.0 | 1371.0 | 0.00% | 0 |
| 1 | 30 | 236141 | 131.2 | 152.3 | 520.0 | 1165.0 | 0.00% | 0 |
| 2 | 60 | 187041 | 103.9 | 192.4 | 667.0 | 1577.0 | 0.00% | 0 |
| 3 | 90 | 287783 | 159.9 | 125.0 | 427.0 | 906.0 | 0.00% | 0 |
| 4 | 120 | 254602 | 141.4 | 141.3 | 507.0 | 1104.0 | 0.00% | 0 |
| 5 | 150 | 134827 | 74.9 | 267.0 | 951.0 | 2549.0 | 0.00% | 0 |
| 6 | 180 | 128265 | 71.3 | 280.4 | 986.0 | 2512.0 | 0.00% | 0 |
| 7 | 210 | 302671 | 168.2 | 118.8 | 344.0 | 851.0 | 0.00% | 0 |

趋势：P95 550.0→344.0 ms，RPS 120.0→168.2，错误率 0.00%→0.00%；P95 斜率 21.6667/窗口。

端点级退化：无（所有端点末窗 P95 未超首窗 1.5 倍）。

## 稳定性 soak_admin（30 分钟窗口）

| 窗口 | 起始分钟 | 样本 | RPS | Avg | P95 | P99 | 错误率 | 缺陷 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 25663 | 14.3 | 277.0 | 560.0 | 917.0 | 0.00% | 0 |
| 1 | 30 | 27627 | 15.4 | 260.4 | 506.0 | 992.0 | 0.00% | 0 |
| 2 | 60 | 22590 | 12.6 | 318.6 | 694.0 | 1273.0 | 0.00% | 0 |
| 3 | 90 | 33093 | 18.4 | 217.5 | 412.0 | 814.0 | 0.00% | 0 |
| 4 | 120 | 29793 | 16.6 | 241.6 | 567.0 | 1171.0 | 0.00% | 0 |
| 5 | 150 | 17132 | 9.5 | 420.1 | 934.0 | 1745.0 | 0.00% | 0 |
| 6 | 180 | 16223 | 9.0 | 443.7 | 925.0 | 1672.0 | 0.00% | 0 |
| 7 | 210 | 35250 | 19.6 | 204.1 | 333.0 | 426.0 | 0.00% | 0 |

趋势：P95 560.0→333.0 ms，RPS 14.3→19.6，错误率 0.00%→0.00%；P95 斜率 16.4405/窗口。

端点级退化：无（所有端点末窗 P95 未超首窗 1.5 倍）。

## 资源水位

| 场景 | 采样 | PID | RSS 首/末/峰 (MB) | CPU 均/峰 | 句柄峰 | DB 增长 (MB) | WAL 峰 | 写 IO 均 (KB/s) | 磁盘余量 (GB) |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| baseline | 21 | 35272 | 100.9/141.4/141.4 | 19.2%/91.5% | 1402 | 0.0 | 0.6 | 132.9 | 3.39 |
| stress | 478 | 31716 | 98.8/244.7/289.0 | 100.2%/160.7% | 1496 | 3.1 | 4.8 | 774.6 | 1.47 |
| soak | 6982 | 35272 | 256.4/198.1/257.1 | 82.4%/134.9% | 514 | 7.0 | 4.8 | 62.3 | 1.51 |

## 端点明细（基线 / 阶梯）


### baseline_c

| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DELETE /api/v1/account/data | 3 | 3.1 | 29.7 | 84.0 | 84.0 | 84.0 | 0.0% | 0 |
| DELETE /api/v1/comments/{comment_id}/like | 3 | 4.4 | 14.7 | 16.0 | 16.0 | 16.0 | 0.0% | 0 |
| DELETE /api/v1/favorites/{episode_id} | 3 | 5.1 | 6.7 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| DELETE /api/v1/subscriptions/channels/{channel_id} | 3 | 5.5 | 7.0 | 8.0 | 8.0 | 8.0 | 0.0% | 0 |
| GET /api/v1/account/data | 3 | 3.4 | 40.7 | 80.0 | 80.0 | 80.0 | 0.0% | 0 |
| GET /api/v1/channels | 3 | 3.6 | 49.0 | 140.0 | 140.0 | 140.0 | 0.0% | 0 |
| GET /api/v1/comments | 3 | 4.3 | 12.3 | 14.0 | 14.0 | 14.0 | 0.0% | 0 |
| GET /api/v1/courses/{channel_id}/progress | 3 | 4.4 | 13.0 | 22.0 | 22.0 | 22.0 | 0.0% | 0 |
| GET /api/v1/episodes/history | 3 | 4.5 | 8.0 | 18.0 | 18.0 | 18.0 | 0.0% | 0 |
| GET /api/v1/episodes/search | 3 | 4.7 | 13.7 | 26.0 | 26.0 | 26.0 | 0.0% | 0 |
| GET /api/v1/episodes/today | 3 | 4.8 | 7.3 | 8.0 | 8.0 | 8.0 | 0.0% | 0 |
| GET /api/v1/episodes/{episode_id} | 3 | 4.8 | 5.0 | 10.0 | 10.0 | 10.0 | 0.0% | 0 |
| GET /api/v1/episodes/{episode_id}/script | 3 | 4.8 | 8.0 | 18.0 | 18.0 | 18.0 | 0.0% | 0 |
| GET /api/v1/favorites | 3 | 5.0 | 13.0 | 17.0 | 17.0 | 17.0 | 0.0% | 0 |
| GET /api/v1/favorites/check/{episode_id} | 3 | 5.0 | 6.7 | 8.0 | 8.0 | 8.0 | 0.0% | 0 |
| GET /api/v1/playlogs/progress/{episode_id} | 3 | 5.1 | 9.0 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /api/v1/playlogs/recent | 3 | 5.1 | 13.0 | 35.0 | 35.0 | 35.0 | 0.0% | 0 |
| GET /api/v1/subscriptions/channels | 3 | 5.4 | 8.0 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /api/v1/subscriptions/templates | 3 | 5.5 | 1.7 | 2.0 | 2.0 | 2.0 | 0.0% | 0 |
| GET /api/v1/users/stats | 3 | 5.5 | 10.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| POST /api/v1/client/report | 3 | 4.3 | 4.0 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /api/v1/comments | 3 | 4.3 | 16.3 | 22.0 | 22.0 | 22.0 | 0.0% | 0 |
| POST /api/v1/comments/{comment_id}/like | 3 | 4.4 | 15.0 | 17.0 | 17.0 | 17.0 | 0.0% | 0 |
| POST /api/v1/favorites | 3 | 5.0 | 12.3 | 14.0 | 14.0 | 14.0 | 0.0% | 0 |
| POST /api/v1/feedbacks | 3 | 5.1 | 26.3 | 29.0 | 29.0 | 29.0 | 0.0% | 0 |
| POST /api/v1/playlogs/progress | 3 | 5.1 | 7.7 | 8.0 | 8.0 | 8.0 | 0.0% | 0 |
| POST /api/v1/subscriptions/channels/{channel_id} | 3 | 5.5 | 9.0 | 10.0 | 10.0 | 10.0 | 0.0% | 0 |
| POST /api/v1/subscriptions/message | 3 | 5.5 | 12.7 | 14.0 | 14.0 | 14.0 | 0.0% | 0 |
| POST /api/v1/users/avatar | 3 | 5.5 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /api/v1/users/profile | 3 | 5.6 | 8.7 | 10.0 | 10.0 | 10.0 | 0.0% | 0 |

### baseline_admin

| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GET /admin/api/v1/about | 3 | 0.2 | 80.7 | 235.0 | 235.0 | 235.0 | 0.0% | 0 |
| GET /admin/api/v1/ads/materials | 3 | 0.2 | 8.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/ads/placements | 3 | 0.2 | 14.0 | 24.0 | 24.0 | 24.0 | 0.0% | 0 |
| GET /admin/api/v1/ads/schedule | 3 | 0.2 | 13.0 | 26.0 | 26.0 | 26.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/audio-profile | 3 | 0.2 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/budget | 3 | 0.2 | 3.7 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/config | 3 | 0.2 | 16.0 | 25.0 | 25.0 | 25.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/download-tts-models/status | 3 | 0.2 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/presets | 3 | 0.2 | 3.0 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/selected-model | 3 | 0.2 | 9.0 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/usage | 3 | 0.2 | 36.0 | 52.0 | 52.0 | 52.0 | 0.0% | 0 |
| GET /admin/api/v1/ai/voices/meta | 3 | 0.2 | 7.0 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| GET /admin/api/v1/assistant/actions | 3 | 0.2 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| GET /admin/api/v1/audit-logs | 3 | 0.2 | 16.7 | 21.0 | 21.0 | 21.0 | 0.0% | 0 |
| GET /admin/api/v1/audit-logs/categories | 3 | 0.2 | 9.3 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/auth/users | 3 | 0.2 | 9.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/auto-review/config | 3 | 0.2 | 11.3 | 20.0 | 20.0 | 20.0 | 0.0% | 0 |
| GET /admin/api/v1/auto-review/history | 3 | 0.2 | 10.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/auto-review/stats | 3 | 0.2 | 18.7 | 21.0 | 21.0 | 21.0 | 0.0% | 0 |
| GET /admin/api/v1/backups | 3 | 0.2 | 26.0 | 37.0 | 37.0 | 37.0 | 0.0% | 0 |
| GET /admin/api/v1/channels | 3 | 0.2 | 8.7 | 17.0 | 17.0 | 17.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/bgm/list | 3 | 0.2 | 7.0 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/book-rss/sources | 3 | 0.2 | 132.7 | 340.0 | 340.0 | 340.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/cover-presets | 3 | 0.2 | 11.3 | 15.0 | 15.0 | 15.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/rss/sources | 3 | 0.2 | 159.3 | 186.0 | 186.0 | 186.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/{channel_id}/book-pool | 3 | 0.2 | 12.7 | 13.0 | 13.0 | 13.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/{channel_id}/book-pool/candidates | 3 | 0.2 | 111.0 | 120.0 | 120.0 | 120.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/{channel_id}/delete-preview | 3 | 0.2 | 56.7 | 71.0 | 71.0 | 71.0 | 0.0% | 0 |
| GET /admin/api/v1/channels/{channel_id}/script-mode | 3 | 0.2 | 13.3 | 20.0 | 20.0 | 20.0 | 0.0% | 0 |
| GET /admin/api/v1/cos/config | 3 | 0.2 | 11.7 | 17.0 | 17.0 | 17.0 | 0.0% | 0 |
| GET /admin/api/v1/cos/move-preview | 3 | 0.2 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/cos/status | 3 | 0.2 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/audit-log | 3 | 0.2 | 9.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/tables | 3 | 0.2 | 41.0 | 63.0 | 63.0 | 63.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/tables/{table}/export | 3 | 0.2 | 42.3 | 84.0 | 84.0 | 84.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/tables/{table}/rows | 3 | 0.2 | 15.3 | 21.0 | 21.0 | 21.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/tables/{table}/schema | 3 | 0.2 | 8.7 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/ebooks/categories | 3 | 0.2 | 2200.7 | 6566.0 | 6566.0 | 6566.0 | 0.0% | 0 |
| GET /admin/api/v1/ebooks/index/status | 3 | 0.4 | 8.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/ebooks/random | 3 | 0.4 | 15.0 | 23.0 | 23.0 | 23.0 | 0.0% | 0 |
| GET /admin/api/v1/ebooks/search | 3 | 0.5 | 22.3 | 41.0 | 41.0 | 41.0 | 0.0% | 0 |
| GET /admin/api/v1/feedbacks | 3 | 0.5 | 16.3 | 27.0 | 27.0 | 27.0 | 0.0% | 0 |
| GET /admin/api/v1/m/dashboard-summary | 3 | 0.5 | 12.0 | 13.0 | 13.0 | 13.0 | 0.0% | 0 |
| GET /admin/api/v1/m/emergency/audit | 3 | 0.5 | 7.7 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/m/inbox | 3 | 0.5 | 17.3 | 30.0 | 30.0 | 30.0 | 0.0% | 0 |
| GET /admin/api/v1/m/maintenance-status | 3 | 0.5 | 8.3 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /admin/api/v1/maintenance/status | 3 | 0.5 | 206.0 | 371.0 | 371.0 | 371.0 | 0.0% | 0 |
| GET /admin/api/v1/maintenance/tasks/{task_id} | 3 | 0.5 | 9.3 | 13.0 | 13.0 | 13.0 | 0.0% | 0 |
| GET /admin/api/v1/materials | 3 | 0.5 | 15.0 | 21.0 | 21.0 | 21.0 | 0.0% | 0 |
| GET /admin/api/v1/materials/aggregate | 3 | 0.5 | 141.3 | 157.0 | 157.0 | 157.0 | 0.0% | 0 |
| GET /admin/api/v1/materials/export | 3 | 0.5 | 741.3 | 911.0 | 911.0 | 911.0 | 0.0% | 0 |
| GET /admin/api/v1/materials/{material_id} | 3 | 0.5 | 7.0 | 8.0 | 8.0 | 8.0 | 0.0% | 0 |
| GET /admin/api/v1/notification/config | 3 | 0.5 | 9.7 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /admin/api/v1/notification/logs | 3 | 0.5 | 11.3 | 15.0 | 15.0 | 15.0 | 0.0% | 0 |
| GET /admin/api/v1/notification/templates | 3 | 0.5 | 8.0 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/queue/config | 3 | 0.5 | 7.3 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/queue/stats | 3 | 0.5 | 7.0 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/queue/tasks | 3 | 0.5 | 14.0 | 17.0 | 17.0 | 17.0 | 0.0% | 0 |
| GET /admin/api/v1/reviews | 3 | 0.5 | 34.3 | 60.0 | 60.0 | 60.0 | 0.0% | 0 |
| GET /admin/api/v1/reviews/{review_id} | 3 | 0.5 | 27.7 | 55.0 | 55.0 | 55.0 | 0.0% | 0 |
| GET /admin/api/v1/scripts | 3 | 0.5 | 9.3 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/scripts/{script_id} | 3 | 0.5 | 8.0 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/channel-health | 3 | 0.5 | 23.7 | 25.0 | 25.0 | 25.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/llm-metrics | 3 | 0.5 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/overview | 3 | 0.5 | 8.3 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/rss-health | 3 | 0.5 | 205.3 | 234.0 | 234.0 | 234.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/trend | 3 | 0.5 | 4.7 | 6.0 | 6.0 | 6.0 | 0.0% | 0 |
| GET /admin/api/v1/system/ffmpeg-status | 3 | 0.5 | 25.0 | 26.0 | 26.0 | 26.0 | 0.0% | 0 |
| GET /admin/api/v1/tunnel/cloudflare/login/status | 3 | 0.5 | 3.3 | 5.0 | 5.0 | 5.0 | 0.0% | 0 |
| GET /admin/api/v1/tunnel/config | 3 | 0.5 | 5.0 | 5.0 | 5.0 | 5.0 | 0.0% | 0 |
| GET /admin/api/v1/tunnel/status | 3 | 0.5 | 6.7 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| GET /admin/api/v1/users | 3 | 0.5 | 10.7 | 12.0 | 12.0 | 12.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows | 3 | 0.5 | 20.0 | 26.0 | 26.0 | 26.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/today | 3 | 0.5 | 9.3 | 14.0 | 14.0 | 14.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/{workflow_id} | 3 | 0.5 | 9.0 | 10.0 | 10.0 | 10.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/{workflow_id}/audio | 3 | 0.5 | 16.0 | 18.0 | 18.0 | 18.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/{workflow_id}/audio/episode | 3 | 0.5 | 8.0 | 9.0 | 9.0 | 9.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/{workflow_id}/audio/proxy | 3 | 0.5 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows/{workflow_id}/audio/tts/{filename} | 3 | 0.5 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| GET /api/health | 3 | 0.5 | 42.7 | 115.0 | 115.0 | 115.0 | 0.0% | 0 |
| GET /api/health/live | 3 | 0.5 | 1.3 | 2.0 | 2.0 | 2.0 | 0.0% | 0 |
| GET /api/health/ready | 3 | 0.5 | 7.0 | 11.0 | 11.0 | 11.0 | 0.0% | 0 |
| GET /api/internal/workflow/{workflow_id} | 3 | 0.5 | 13.3 | 20.0 | 20.0 | 20.0 | 0.0% | 0 |
| POST /admin/api/v1/ads/materials | 3 | 0.2 | 4.0 | 7.0 | 7.0 | 7.0 | 0.0% | 0 |
| POST /admin/api/v1/ads/placements | 3 | 0.2 | 3.0 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/auth/change-password | 3 | 0.2 | 3.0 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/auth/login | 3 | 0.2 | 646.3 | 731.0 | 731.0 | 731.0 | 0.0% | 0 |
| POST /admin/api/v1/auth/users | 3 | 0.2 | 2.7 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/channels | 3 | 0.2 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/channels/bgm/upload | 3 | 0.2 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/channels/{channel_id}/book-pool/items | 3 | 0.2 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/channels/{channel_id}/book-pool/items/{item_id}/move | 3 | 0.2 | 4.3 | 5.0 | 5.0 | 5.0 | 0.0% | 0 |
| POST /admin/api/v1/channels/{channel_id}/icon | 3 | 0.2 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/m/device/register | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/m/inbox/mark-read | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/m/push/register | 3 | 0.5 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/maintenance/cache | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/maintenance/database | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/maintenance/logs | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/maintenance/workflow-chain | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/materials | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/materials/upload | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/notification/templates/{template_id}/preview | 3 | 0.5 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| POST /admin/api/v1/reviews/batch-action | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/reviews/{review_id}/action | 3 | 0.5 | 2.3 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| POST /admin/api/v1/users/{user_id}/toggle-status | 3 | 0.5 | 4.3 | 6.0 | 6.0 | 6.0 | 0.0% | 0 |
| PUT /admin/api/v1/ads/placements/{placement_id} | 3 | 0.2 | 2.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/auth/users/{admin_id} | 3 | 0.2 | 2.3 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /admin/api/v1/auto-review/config | 3 | 0.2 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/channels/{channel_id} | 3 | 0.2 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/channels/{channel_id}/book-pool/order | 3 | 0.2 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/channels/{channel_id}/script-mode | 3 | 0.2 | 4.0 | 5.0 | 5.0 | 5.0 | 0.0% | 0 |
| PUT /admin/api/v1/channels/{channel_id}/script-mode/schedule | 3 | 0.2 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/feedbacks/{feedback_id}/status | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/materials/{material_id} | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /admin/api/v1/notification/config | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /admin/api/v1/notification/templates/{template_id} | 3 | 0.5 | 3.7 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |
| PUT /admin/api/v1/queue/config | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /admin/api/v1/queue/tasks/{workflow_id}/priority | 3 | 0.5 | 3.0 | 3.0 | 3.0 | 3.0 | 0.0% | 0 |
| PUT /admin/api/v1/scripts/{script_id}/segments | 3 | 0.5 | 3.3 | 4.0 | 4.0 | 4.0 | 0.0% | 0 |

### stress_c_read_200

| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GET /api/v1/channels | 2557 | 28.6 | 228.9 | 313.0 | 361.0 | 855.0 | 0.0% | 0 |
| GET /api/v1/episodes/history | 2539 | 28.4 | 239.4 | 310.0 | 356.0 | 1343.0 | 0.0% | 0 |
| GET /api/v1/episodes/search | 2440 | 27.4 | 1077.1 | 1429.0 | 1786.0 | 2405.0 | 0.0% | 0 |
| GET /api/v1/episodes/today | 6539 | 72.4 | 953.9 | 1338.0 | 1543.0 | 2039.0 | 0.0% | 0 |
| GET /api/v1/episodes/{episode_id} | 2514 | 28.1 | 222.3 | 307.0 | 333.0 | 442.0 | 0.0% | 0 |
| GET /api/v1/episodes/{episode_id}/script | 2487 | 27.9 | 225.0 | 309.0 | 340.0 | 453.0 | 0.0% | 0 |
| GET /api/v1/favorites | 1191 | 13.4 | 317.0 | 331.0 | 1339.0 | 2540.0 | 0.0% | 0 |
| GET /api/v1/playlogs/progress/{episode_id} | 1182 | 13.3 | 1386.3 | 1856.0 | 2155.0 | 2822.0 | 0.0% | 0 |
| GET /api/v1/playlogs/recent | 1184 | 13.3 | 269.2 | 314.0 | 385.0 | 1916.0 | 0.0% | 0 |
| GET /api/v1/subscriptions/channels | 1173 | 13.4 | 1043.3 | 1410.0 | 1725.0 | 2280.0 | 0.0% | 0 |
| GET /api/v1/users/stats | 1166 | 13.3 | 1569.1 | 2055.0 | 2247.0 | 2818.0 | 0.0% | 0 |

### stress_c_write_50

| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DELETE /api/v1/favorites/{episode_id} | 1095 | 12.2 | 643.9 | 857.0 | 935.0 | 1205.0 | 0.0% | 0 |
| DELETE /api/v1/subscriptions/channels/{channel_id} | 537 | 6.0 | 665.4 | 879.0 | 939.0 | 1225.0 | 0.0% | 0 |
| POST /api/v1/comments | 2297 | 25.6 | 668.4 | 887.0 | 963.0 | 1241.0 | 0.0% | 0 |
| POST /api/v1/favorites | 1119 | 12.5 | 647.5 | 872.0 | 934.0 | 1219.0 | 0.0% | 0 |
| POST /api/v1/feedbacks | 533 | 6.0 | 708.6 | 917.0 | 973.0 | 1322.0 | 0.0% | 0 |
| POST /api/v1/playlogs/progress | 4648 | 51.7 | 16.8 | 31.0 | 37.0 | 53.0 | 0.0% | 0 |
| POST /api/v1/subscriptions/channels/{channel_id} | 541 | 6.0 | 665.4 | 882.0 | 962.0 | 1211.0 | 0.0% | 0 |
| PUT /api/v1/users/profile | 532 | 5.9 | 10.7 | 23.0 | 30.0 | 41.0 | 0.0% | 0 |

### stress_admin_read_50

| 端点 | 样本 | RPS | Avg | P90 | P95 | P99 | 错误率 | 5xx/000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GET /admin/api/v1/audit-logs | 562 | 6.3 | 358.9 | 422.0 | 564.0 | 2246.0 | 0.0% | 0 |
| GET /admin/api/v1/channels | 565 | 6.3 | 45.1 | 60.0 | 78.0 | 264.0 | 0.0% | 0 |
| GET /admin/api/v1/db-admin/tables/{table}/rows | 557 | 6.2 | 565.3 | 627.0 | 801.0 | 3016.0 | 0.0% | 0 |
| GET /admin/api/v1/feedbacks | 558 | 6.3 | 300.2 | 360.0 | 463.0 | 1984.0 | 0.0% | 0 |
| GET /admin/api/v1/m/dashboard-summary | 1776 | 19.8 | 282.1 | 356.0 | 444.0 | 1969.0 | 0.0% | 0 |
| GET /admin/api/v1/m/inbox | 560 | 6.3 | 425.5 | 501.0 | 578.0 | 2058.0 | 0.0% | 0 |
| GET /admin/api/v1/materials | 1131 | 12.6 | 370.6 | 418.0 | 521.0 | 2349.0 | 0.0% | 0 |
| GET /admin/api/v1/queue/tasks | 565 | 6.3 | 503.5 | 620.0 | 720.0 | 2167.0 | 0.0% | 0 |
| GET /admin/api/v1/reviews | 1150 | 12.8 | 767.0 | 973.0 | 1029.0 | 1989.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/overview | 1795 | 20.0 | 176.3 | 224.0 | 289.0 | 1168.0 | 0.0% | 0 |
| GET /admin/api/v1/stats/trend | 551 | 6.2 | 40.6 | 60.0 | 77.0 | 195.0 | 0.0% | 0 |
| GET /admin/api/v1/workflows | 1168 | 13.0 | 656.9 | 783.0 | 860.0 | 2539.0 | 0.0% | 0 |

## 覆盖统计

- executed: 150
- static-only: 35
- probed: 55
- not-run: 2
- sse: 1