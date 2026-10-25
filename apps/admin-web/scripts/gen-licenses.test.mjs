/**
 * 开源清单生成器的测试（T02691 / FR-UX-404）
 *
 * 生成器的价值全在「机器读到的真话」：许可字段写法千奇百怪（PyMuPDF 的双许可长句、
 * 分类器兜底、UNKNOWN 占位），任何一条被吞掉，合规清单就会少一行或写错一行。
 * 这里把归一化、仓库地址、标记块替换逐条钉住，最后再对真实仓库的生成结果做一次对账。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  UNKNOWN_LICENSE,
  parseRequirements,
  licenseFromPyMeta,
  licenseFromNpmPackage,
  normalizeRepoUrl,
  repoFromPyMeta,
  repoFromNpmPackage,
  buildEntries,
  renderEntries,
  replaceLicenseBlock,
  LICENSES_START,
  LICENSES_END,
} from './gen-licenses.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = resolve(WEB_ROOT, '../..')

/** validate-nav.mjs 的 readLicenseTable 用的同一条正则：生成结果必须能被它逐条解析 */
const TABLE_ROW = /\{\s*name:\s*'([^']+)',\s*version:\s*'([^']+)'/g

test('requirements 解析：剥掉 extras/注释，按归一化名字去重', () => {
  const text = [
    '# ==== 框架 ====',
    'fastapi==0.110.0',
    'uvicorn[standard]==0.27.0   # ASGI 服务器',
    'PyMuPDF==1.28.2',
    'pyyaml==6.0.1',
    'PyYAML==9.9.9',
    'not-a-pin>=1.0',
    '',
  ].join('\n')
  assert.deepEqual(parseRequirements(text), [
    { name: 'fastapi', version: '0.110.0' },
    { name: 'uvicorn', version: '0.27.0' },
    { name: 'PyMuPDF', version: '1.28.2' },
    { name: 'pyyaml', version: '6.0.1' },
  ])
})

test('仓库地址归一：git+/ssh/scp/git://、npm 简写与 .git、片段都收敛成 https', () => {
  const cases = [
    ['git+https://github.com/a/b.git', 'https://github.com/a/b'],
    ['git+ssh://git@github.com:a/b.git', 'https://github.com/a/b'],
    ['ssh://git@github.com/a/b.git', 'https://github.com/a/b'],
    ['git@github.com:a/b.git', 'https://github.com/a/b'],
    ['git://github.com/a/b.git', 'https://github.com/a/b'],
    ['http://github.com/a/b', 'https://github.com/a/b'],
    ['github:a/b', 'https://github.com/a/b'],
    ['https://github.com/a/b/#readme', 'https://github.com/a/b'],
    // eslint/globals 的 package.json 就把 repository 写成 npm 简写，不展开会是死链
    ['eslint/eslint', 'https://github.com/eslint/eslint'],
    ['some.user/repo-name', 'https://github.com/some.user/repo-name'],
    ['user/repo.git', 'https://github.com/user/repo'],
    ['', ''],
  ]
  for (const [input, want] of cases) assert.equal(normalizeRepoUrl(input), want, input)
})

test('npm 许可：字符串/对象/数组都能读，取不到落「未知」而不是消失', () => {
  assert.equal(licenseFromNpmPackage({ license: 'MIT' }), 'MIT')
  assert.equal(licenseFromNpmPackage({ license: { type: 'Apache-2.0' } }), 'Apache-2.0')
  assert.equal(licenseFromNpmPackage({ licenses: [{ type: 'MIT' }, { type: 'Apache-2.0' }] }), 'MIT OR Apache-2.0')
  assert.equal(licenseFromNpmPackage({ license: 'MIT License' }), 'MIT')
  // 这是「许可取不到」的 fixture：包在、字段没有 → 条目保留但明确标未知
  assert.equal(licenseFromNpmPackage({ name: 'no-license-fixture' }), UNKNOWN_LICENSE)
  assert.equal(licenseFromNpmPackage({ license: 'UNKNOWN' }), UNKNOWN_LICENSE)
  assert.equal(licenseFromNpmPackage(null), UNKNOWN_LICENSE)
})

test('PyPI 许可：真实长句/分类器/具体写法都收敛成 SPDX', () => {
  // 三条来自本仓库实际安装的包（PyMuPDF、slowapi、cos-python-sdk-v5）
  assert.equal(
    licenseFromPyMeta({ license: 'Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License' }),
    'AGPL-3.0',
  )
  assert.equal(licenseFromPyMeta({ license: 'MIT', classifiers: ['License :: OSI Approved :: MIT License'] }), 'MIT')
  assert.equal(licenseFromPyMeta({ license: 'MIT' }), 'MIT')
  // 具体写法优先于泛化分类器：feedparser 是 BSD-2-Clause，分类器只写「BSD License」
  assert.equal(
    licenseFromPyMeta({
      license: 'BSD-2-Clause',
      classifiers: ['License :: OSI Approved :: BSD License'],
    }),
    'BSD-2-Clause',
  )
  // 没有 License 字段时用分类器兜底（edge-tts）
  assert.equal(
    licenseFromPyMeta({
      license: null,
      classifiers: ['License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)'],
    }),
    'LGPL-3.0',
  )
  // PEP 639 的 License-Expression 优先（openai）
  assert.equal(licenseFromPyMeta({ license: null, licenseExpression: 'Apache-2.0' }), 'Apache-2.0')
  // 复合写法保留两个许可，不悄悄只留一个
  assert.equal(licenseFromPyMeta({ license: 'BSD-3-Clause and Public-Domain' }), 'BSD-3-Clause AND Public-Domain')
  // 这是「元数据缺字段」的 fixture：条目保留、许可明确标未知
  assert.equal(licenseFromPyMeta({}), UNKNOWN_LICENSE)
  assert.equal(licenseFromPyMeta({ license: 'UNKNOWN' }), UNKNOWN_LICENSE)
})

test('PyPI 仓库：优先 Source/Repository，其次 Home-page，不把 changelog/issues 当仓库', () => {
  assert.equal(
    repoFromPyMeta('x', {
      homePage: 'https://example.com/x',
      projectUrls: [
        { label: 'Homepage', url: 'https://example.com/x' },
        { label: 'Source', url: 'https://github.com/a/x.git' },
      ],
    }),
    'https://github.com/a/x',
  )
  // edge-tts 实际元数据：只有 Bug Tracker 挂在 github，Home-page 才是仓库
  assert.equal(
    repoFromPyMeta('edge-tts', {
      homePage: 'https://github.com/rany2/edge-tts',
      projectUrls: [{ label: 'Bug Tracker', url: 'https://github.com/rany2/edge-tts/issues' }],
    }),
    'https://github.com/rany2/edge-tts',
  )
  // 一条 url 都没有时退到 PyPI 项目页，仍然是可用链接
  assert.equal(repoFromPyMeta('lonely', null), 'https://pypi.org/project/lonely/')
})

test('npm 仓库：repository 对象/字符串都认，缺失退到 npmjs 包页', () => {
  assert.equal(
    repoFromNpmPackage('vue', { repository: { type: 'git', url: 'git+https://github.com/vuejs/core.git' } }),
    'https://github.com/vuejs/core',
  )
  assert.equal(repoFromNpmPackage('vue-chartjs', { repository: 'git+ssh://git@github.com:a/b.git' }), 'https://github.com/a/b')
  // eslint / globals 就是这样写的：不展开成绝对地址，关于页的 <a :href> 会变成站内死链
  assert.equal(repoFromNpmPackage('eslint', { repository: 'eslint/eslint' }), 'https://github.com/eslint/eslint')
  assert.equal(repoFromNpmPackage('@scope/pkg', {}), 'https://www.npmjs.com/package/%40scope%2Fpkg')
})

test('buildEntries：合并、排序、未知许可原样保留，不静默丢条目', () => {
  const entries = buildEntries({
    npm: [
      { name: 'vue', version: '^3.4.0', pkg: { license: 'MIT', repository: 'https://github.com/vuejs/core.git' } },
      { name: 'NoMeta', version: '^1.0.0', pkg: null },
    ],
    py: [{ name: 'fastapi', version: '0.110.0', meta: { licenseExpression: 'MIT' } }],
  })
  assert.deepEqual(
    entries.map((e) => e.name),
    ['fastapi', 'NoMeta', 'vue'],
    '排序必须忽略大小写，否则同一次的稳定输出会变',
  )
  assert.equal(entries.find((e) => e.name === 'NoMeta').license, UNKNOWN_LICENSE)
  assert.equal(entries.find((e) => e.name === 'NoMeta').repo, 'https://www.npmjs.com/package/NoMeta')
})

test('渲染与标记块替换：只动块内、可重复执行、缺标记直接拒绝', () => {
  const entries = [
    { name: 'vue', version: '^3.4.0', license: 'MIT', repo: 'https://github.com/vuejs/core' },
    { name: 'zlib', version: '1.0.0', license: UNKNOWN_LICENSE, repo: 'https://example.com' },
  ]
  const declaration = renderEntries(entries)
  assert.match(declaration, /^const licenses = \[/)
  // 单引号必须转义，否则生成的就是坏代码（真实包名不会带引号，属防御性用例）
  const quoted = renderEntries([{ name: "o'brien", version: '1.0.0', license: 'MIT', repo: 'https://example.com' }])
  assert.match(quoted, /o\\'brien/)
  const rows = [...declaration.matchAll(TABLE_ROW)]
  assert.deepEqual(rows.map((m) => [m[1], m[2]]), [
    ['vue', '^3.4.0'],
    ['zlib', '1.0.0'],
  ])

  const source = `const before = 1\n${LICENSES_START}\nconst licenses = []\n${LICENSES_END}\nconst after = 2\n`
  const once = replaceLicenseBlock(source, declaration)
  assert.equal(replaceLicenseBlock(once, declaration), once, '同一份输入重复生成必须字节级一致')
  assert.ok(once.startsWith('const before = 1\n'))
  assert.ok(once.endsWith(`${LICENSES_END}\nconst after = 2\n`))
  assert.equal(once.match(/const licenses = \[/g).length, 1)

  assert.throws(() => replaceLicenseBlock('const licenses = []\n', declaration), /缺少/)
  const dup = `${LICENSES_START}\n${LICENSES_END}\n${LICENSES_START}\n${LICENSES_END}\n`
  assert.throws(() => replaceLicenseBlock(dup, declaration), /多次/)
})

test('真实仓库：生成表条目数等于两份清单之和，特殊许可与标记都在位', () => {
  const about = readFileSync(join(WEB_ROOT, 'src/views/about/About.vue'), 'utf8')
  assert.ok(about.includes(LICENSES_START) && about.includes(LICENSES_END), 'About.vue 缺少生成标记块')

  const pkg = JSON.parse(readFileSync(join(WEB_ROOT, 'package.json'), 'utf8'))
  const npmCount = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies }).length
  const py = parseRequirements(readFileSync(join(REPO_ROOT, 'backend/requirements.txt'), 'utf8'))

  const block = about.slice(about.indexOf(LICENSES_START), about.indexOf(LICENSES_END))
  const rows = [...block.matchAll(/\{\s*name:\s*'([^']+)',\s*version:\s*'([^']+)',\s*license:\s*'([^']+)',\s*repo:\s*'([^']+)'\s*\}/g)]
  assert.equal(rows.length, npmCount + py.length, '条目数与 npm + requirements 去重数对不上')
  for (const row of rows) {
    assert.ok(row[3], `${row[1]} 的 repo 为空`)
    assert.ok(row[4], `${row[1]} 的 license 为空`)
  }

  const byName = new Map(rows.map((m) => [m[1], { version: m[2], license: m[3], repo: m[4] }]))
  for (const [name, license] of [
    ['PyMuPDF', 'AGPL-3.0'],
    ['slowapi', 'MIT'],
    ['cos-python-sdk-v5', 'MIT'],
  ]) {
    assert.equal(byName.get(name)?.license, license, `${name} 的许可名不对`)
  }
  // 未安装/无元数据的包必须落「未知」而不是被删掉——真实样例：NoMeta 在上一用例覆盖，
  // 这里确认未知文案只出现在确有缺失时，不会把正常包也标成未知
  assert.equal(rows.filter((m) => m[3] === UNKNOWN_LICENSE).length, 0)
})
