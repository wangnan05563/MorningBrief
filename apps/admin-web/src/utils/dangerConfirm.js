/**
 * 破坏性操作统一确认（T02490 / FR-UX-202）
 *
 * 规范（PRD §6.3）：`动作 + 对象 + 影响条数 + 不可逆声明`，
 * 高风险/批量动作再要求输入确认词，预览失败禁止提交。
 * 之前每个页面各写一句 confirm，最常见的缺项是「影响条数」和「不可逆声明」。
 */
import { h } from 'vue'
import { ElInput } from 'element-plus'
import { ElMessage, ElMessageBox } from './message'

// 确认框正文里的对象名来自抓取内容（RSS 标题、素材名），必须转义后再走 HTML 渲染
const escapeHtml = (v) =>
  String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// scope/lines 支持字符串或数组：数组每项渲染成一行，调用方不必再拼 <br/>
const toLines = (v) => {
  if (Array.isArray(v)) return v.filter((x) => x !== undefined && x !== null && x !== '')
  if (v === undefined || v === null || v === '') return []
  return String(v).split('\n')
}

/** 拼出规范的确认正文：标题行 + 影响范围 + 不可逆声明 */
export function buildDangerText({ action, target, scope, irreversible, lines = [] }) {
  const head = `<div style="font-weight:600;margin-bottom:8px">${escapeHtml(action)}：${escapeHtml(target)}</div>`
  const scopeLines = toLines(scope)
  const rows = [
    ...scopeLines.map(
      (l, i) =>
        `<div>${i === 0 ? '影响范围：' : '&nbsp;&nbsp;'}${escapeHtml(l)}</div>`,
    ),
    ...toLines(lines).map((l) => `<div>${escapeHtml(l)}</div>`),
    `<div style="margin-top:8px;color:var(--el-color-danger)">${escapeHtml(
      irreversible || '此操作不可恢复，且没有回收站/撤销入口。',
    )}</div>`,
  ].join('')
  return `${head}${rows}`
}

/**
 * @param action 动作名（如「删除频道」）
 * @param target 影响对象（中文名，如「频道「早间资讯」」）
 * @param scope 条数/范围描述（字符串或数组，数组每项一行）
 * @param lines 额外明细行（级联清单、保留天数等）
 * @param irreversible 不可逆声明，缺省给通用文案
 * @param confirmWord 需要逐字输入的确认词（表名 / DELETE）；不传则只需点确认
 * @returns Promise<boolean> 用户是否确认执行
 */
export async function dangerConfirm(opts) {
  const { confirmWord, confirmLabel = '确认执行', ...rest } = opts
  const message = buildDangerText(rest)
  try {
    if (confirmWord) {
      await ElMessageBox.prompt(
        `${message}<div style="margin-top:8px">请输入 <b>${escapeHtml(confirmWord)}</b> 以确认：</div>`,
        '危险操作确认',
        {
          dangerouslyUseHTMLString: true,
          type: 'error',
          confirmButtonText: confirmLabel,
          cancelButtonText: '取消',
          inputPlaceholder: confirmWord,
          inputValidator: (v) =>
            (v || '').trim() === confirmWord || `请逐字输入 ${confirmWord}`,
        },
      )
    } else {
      await ElMessageBox.confirm(message, '危险操作确认', {
        dangerouslyUseHTMLString: true,
        type: 'warning',
        confirmButtonText: confirmLabel,
        cancelButtonText: '取消',
      })
    }
    return true
  } catch {
    // 取消与遮罩关闭都视为「不执行」
    return false
  }
}

/**
 * 带「操作原因」输入的高危确认（T03321）。
 *
 * 与 `dangerConfirm` 同一套正文规范，区别是在确认框里多一个可选文本域：
 * 原因随请求一起提交，最终落进审计 `detail.reason`，与读口「原因」列对齐。
 * 原因不是必填——缺省空串，避免打断「急着止损」的操作；但填了就必须带出去。
 *
 * @returns Promise<{confirmed: boolean, reason: string}>
 */
export async function dangerConfirmWithReason(opts) {
  const {
    confirmWord,
    confirmLabel = '确认执行',
    reasonLabel = '操作原因（可选，会写入审计日志）',
    reasonPlaceholder = '例如：频道下线，素材不再使用',
    ...rest
  } = opts
  const state = { reason: '', confirm: '' }
  const message = buildDangerText(rest)

  const children = [h('div', { innerHTML: message })]
  children.push(
    h('div', { style: 'margin-top:8px' }, [
      h('div', { style: 'margin-bottom:4px' }, reasonLabel),
      h(ElInput, {
        type: 'textarea',
        rows: 2,
        maxlength: 200,
        showWordLimit: true,
        placeholder: reasonPlaceholder,
        'onUpdate:modelValue': (v) => {
          state.reason = v || ''
        },
      }),
    ]),
  )
  if (confirmWord) {
    children.push(
      h('div', { style: 'margin-top:8px' }, [
        `请输入 `,
        h('b', null, confirmWord),
        ` 以确认：`,
        h(ElInput, {
          placeholder: confirmWord,
          'onUpdate:modelValue': (v) => {
            state.confirm = v || ''
          },
        }),
      ]),
    )
  }

  try {
    // 可调用形态的签名是 ElMessageBox(options, appContext)，不是 (message, title, options)；
    // 按后者传会把 title 串当成 appContext，渲染时炸成「Object prototype may only be an Object or null」
    await ElMessageBox({
      title: '危险操作确认',
      message: h('div', null, children),
      type: 'error',
      confirmButtonText: confirmLabel,
      cancelButtonText: '取消',
      closeOnClickModal: false,
      beforeClose: (action, instance, done) => {
        if (action !== 'confirm') return done()
        if (confirmWord && state.confirm.trim() !== confirmWord) {
          ElMessage.error(`请逐字输入 ${confirmWord}`)
          return
        }
        done()
      },
    })
    return { confirmed: true, reason: state.reason.trim() }
  } catch (e) {
    // Element Plus 用字符串 'cancel' / 'close' reject 表示用户放弃；
    // 其它异常是确认框自身出错，一并当成「用户取消」会把故障伪装成一次正常放弃
    if (e !== 'cancel' && e !== 'close') {
      console.error('[dangerConfirmWithReason] 确认框未能弹出，按未确认处理：', e)
    }
    return { confirmed: false, reason: '' }
  }
}
