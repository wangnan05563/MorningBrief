/**
 * PRD §7 接口路径与真实路由对账（T02885）
 *
 * 背景：PRD 曾把数据库维护的接口写成 `PUT /admin/api/v1/db/...`，而真实路由是
 * `PATCH /admin/api/v1/db-admin/...`。PRD 是验收口径的唯一来源，路径写错会让
 * 验收脚本/手工 curl 直接 404，而且不会有人因此变红。
 *
 * 这里不维护第二份「期望路径」清单，而是直接读路由源码：
 * PRD 表格里的动词与路径必须能在 `backend/app/routers/admin/db_admin.py`
 * 找到对应的 @router 装饰器。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../../../', import.meta.url))
const prd = readFileSync(join(root, 'docs', '需求规格说明书-UX优化.md'), 'utf8')
const router = readFileSync(
  join(root, 'backend', 'app', 'routers', 'admin', 'db_admin.py'),
  'utf8',
)

describe('PRD §7：数据库维护接口路径与路由一致', () => {
  it('INT-UX-01 行更新是 PATCH /db-admin（主键为 path 参数）', () => {
    assert.match(
      prd,
      /INT-UX-01 \| `PATCH \/admin\/api\/v1\/db-admin\/tables\/\{t\}\/rows\/\{pk\}`/,
    )
    assert.match(
      router,
      /@router\.patch\("\/tables\/\{table\}\/rows\/\{pk_value:path\}"\)/,
    )
  })

  it('INT-UX-02 导入是 POST /db-admin', () => {
    assert.match(
      prd,
      /INT-UX-02 \| `POST \/admin\/api\/v1\/db-admin\/tables\/\{t\}\/import`/,
    )
    assert.match(router, /@router\.post\("\/tables\/\{table\}\/import"\)/)
  })

  it('PRD 不得再出现不存在的 /admin/api/v1/db/ 前缀', () => {
    assert.equal(
      /INT-UX-0[12] \| `[^`]*\/admin\/api\/v1\/db\//.test(prd),
      false,
      'INT-UX-01/02 仍指向不存在的 /db/ 前缀',
    )
  })
})
