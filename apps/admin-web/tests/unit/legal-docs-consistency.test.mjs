/**
 * T02690：政策文本单一来源门禁
 *
 * 用户协议/隐私政策正文只维护一份（小程序 pages/{agreement,privacy} 的 data.sections），
 * docs/legal/*.md 是由它渲染的审阅副本。这组用例锁三件事：
 * 1. 两份 md 与小程序常量逐字一致（少一节、改一字都红）；
 * 2. 比对器有牙齿：内容漂移、文档缺失、把 A 的正文配 B 的路径（接错对象）都必须被抓到；
 * 3. md ↔ 结构往返稳定（parse → render 逐字相等），否则「重新生成」会引入无意义 diff。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/legal-docs-consistency.test.mjs
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  LEGAL_DOCS,
  buildDocs,
  compareAll,
  extractSections,
  parseMarkdown,
  readDoc,
  renderMarkdown,
} from '../../../../scripts/legal-docs.mjs'

describe('政策文本与小程序常量一致', () => {
  it('两份文档逐字一致（标题、小节顺序、正文）', () => {
    assert.deepEqual(compareAll(), [])
  })

  it('小节数与标题顺序锁定为小程序现值', () => {
    const built = buildDocs()
    const terms = built.find((b) => b.key === 'terms')
    const privacy = built.find((b) => b.key === 'privacy')
    const titles = (item) => parseMarkdown(item.expected).sections.map((s) => s.title)
    assert.equal(terms.doc, 'docs/legal/用户协议.md')
    assert.equal(privacy.doc, 'docs/legal/隐私政策.md')
    assert.deepEqual(titles(terms), ['一、服务说明', '二、用户注册与登录', '三、内容来源', '四、用户行为规范', '五、服务变更与终止', '六、免责声明', '七、协议修改'])
    assert.deepEqual(titles(privacy), ['一、信息收集', '二、信息使用', '三、信息存储与保护', '四、信息共享', '五、Cookie 与缓存', '六、未成年人保护', '七、您的权利', '八、政策变更'])
  })

  it('md ↔ 结构往返稳定：parse 后再 render 与原文逐字相同', () => {
    for (const meta of LEGAL_DOCS) {
      const md = readDoc(meta.doc)
      const again = renderMarkdown(parseMarkdown(md), meta)
      assert.equal(again, md, `${meta.doc} 往返不一致`)
    }
  })

  it('小程序页面确由 Page({ data }) 定义，且标题与小节非空', () => {
    for (const meta of LEGAL_DOCS) {
      const got = extractSections(readDoc(meta.page))
      assert.ok(got.title.length > 1)
      assert.ok(got.sections.length >= 7)
      for (const s of got.sections) {
        assert.ok(s.title && s.content, `${meta.page} 存在空小节`)
      }
    }
  })
})

describe('比对器有牙齿（反例）', () => {
  it('正文改一个字就必须报红', () => {
    const built = buildDocs().map((b) => {
      if (b.key !== 'terms') return b
      const md = parseMarkdown(b.expected)
      md.sections[0] = { ...md.sections[0], content: md.sections[0].content + '（篡改）' }
      return { ...b, expected: renderMarkdown(md, b) }
    })
    const diffs = compareAll(built)
    assert.equal(diffs.length, 1)
    assert.match(diffs[0].reason, /一、服务说明/)
  })

  it('少一节必须报红，且点名缺的是哪一节', () => {
    const built = buildDocs().map((b) => {
      if (b.key !== 'privacy') return b
      const md = parseMarkdown(b.expected)
      md.sections = md.sections.slice(0, -1)
      return { ...b, expected: renderMarkdown(md, b) }
    })
    const diffs = compareAll(built)
    assert.ok(diffs.some((d) => d.reason.includes('小节不一致')), JSON.stringify(diffs))
  })

  it('接错对象：把隐私政策的正文配到用户协议路径必须报红', () => {
    const built = buildDocs()
    const terms = built.find((b) => b.key === 'terms')
    const privacy = built.find((b) => b.key === 'privacy')
    const swapped = built.map((b) => (b.key === 'terms' ? { ...b, expected: privacy.expected } : b))
    assert.ok(compareAll(swapped).length > 0, '用户协议路径下放隐私政策正文却判一致')
    // 反之亦然：拿正确正文配错路径同样是错
    const wrongPath = built.map((b) => (b.key === 'terms' ? { ...b, doc: 'docs/legal/隐私政策.md', expected: terms.expected } : b))
    assert.ok(compareAll(wrongPath).length > 0, '路径接错却判一致')
  })

  it('文档缺失必须报「文件不存在」而不是静默通过', () => {
    const built = buildDocs().map((b) => ({ ...b, doc: 'docs/legal/__不存在__.md' }))
    const diffs = compareAll(built)
    assert.equal(diffs.length, 2)
    for (const d of diffs) assert.equal(d.reason, '文件不存在')
  })
})
