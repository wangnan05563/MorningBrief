/**
 * COS 对象键的目录名归一（T02534 / H8）。
 *
 * H8 的原始表现：后端 `list_directory` 返回的 folders **自带结尾斜杠**（"sub1/"），
 * 行内 name 与表格显示都含 "/"；`openRename` 把含斜杠的 name 原样预填进「新名称」，
 * `confirmRename` 再**无条件补一个 "/"** → 用户「不改动直接点确定」时
 * destKey = "prefix/sub1//"。它 ≠ row.key，所以连原有的短路返回都拦不住，
 * 整个目录被搬进畸形前缀，列表随即出现空白子层级——等效数据错位，且全程无提示。
 *
 * 单独成模块的原因：这条链路的后果是**改坏数据**，判定必须能被直接断言，
 * 而不是靠抓 .vue 源码里的字符串（M2 的变异探针已经证明文本门断不掉标识符级破坏）。
 */

/** 名称段一律剥掉首尾斜杠：尾斜杠来自后端 folders 口径，首斜杠来自用户粘贴。 */
export function normalizeSegment(raw) {
  return String(raw ?? '').trim().replace(/^\/+|\/+$/g, '')
}

/**
 * 本弹窗只做**同级**重命名，所以名称段里不允许再出现斜杠：
 * 带斜杠等于把对象甩进另一层前缀，而当前列表按 prefix 过滤，
 * 用户只会看到「它莫名其妙不见了」。返回 null 表示该名称不可用。
 */
export function validateSegment(raw) {
  const seg = normalizeSegment(raw)
  if (!seg) return { ok: false, reason: '新名称不能为空' }
  if (seg.includes('/')) return { ok: false, reason: '名称不能包含 /（此处只做同级重命名）' }
  return { ok: true, segment: seg }
}

/**
 * 目标键 = 当前前缀 + 归一后的名称段（目录补**恰好一个**尾斜杠）。
 * 这里就是 "sub1//" 的诞生地：补斜杠必须建立在已剥尾斜杠的名字上。
 */
export function buildDestKey(currentPrefix, rawName, isFolder) {
  const seg = normalizeSegment(rawName)
  if (!seg) return null
  return `${currentPrefix || ''}${seg}${isFolder ? '/' : ''}`
}
