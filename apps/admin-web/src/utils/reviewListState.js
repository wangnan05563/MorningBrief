/**
 * 移动端审核列表的重载合并（T02544 切片 6 / I6）
 *
 * 缺陷：`act()` 处理完一条后 `await load()`，而 `load()` 会重新构造整批行对象
 * （`expanded:false / detail:null / audio* 归零`）。正在看的那条详情、已展开的其它条、
 * 以及滚动位置一起被抹掉——用户处理完一条就得重新找到刚才看的位置。
 *
 * 修法：按 id 复用旧行对象，只让服务端字段覆盖上去。对象身份不变 → v-for 不会重挂载，
 * 展开态与已加载的详情/音频自然保留。纯函数便于 `node --test` 直接断言。
 */

/** 新行的客户端态默认值（服务端不返回这些字段） */
export function decorateReviewRow(raw) {
  return {
    ...raw,
    busy: false,
    expanded: false,
    detail: null,
    loadingDetail: false,
    // B12：语音内容的三种来源与播放态，展开时按 detail 判定
    audioMode: 'none',
    audioSrc: '',
    audioError: '',
    audioLoading: false,
    audioToken: 0,
  }
}

/**
 * @param {Array<object>} prevRows 当前列表（可能含展开/详情/音频态）
 * @param {Array<object>} rows 服务端新返回的行
 * @returns {Array<object>} 新列表；命中的行是**旧对象本身**（就地覆盖服务端字段）
 */
export function mergeReviewRows(prevRows, rows) {
  const prev = new Map()
  for (const row of prevRows || []) prev.set(String(row.id), row)
  return (rows || []).map((raw) => {
    const old = prev.get(String(raw.id))
    if (old) return Object.assign(old, raw)
    return decorateReviewRow(raw)
  })
}
