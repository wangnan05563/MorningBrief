/**
 * ElMessage / ElMessageBox 安全包装器
 *
 * 核心策略：在所有弹窗调用入口处拦截，
 * 只要页面不可见或正在恢复，就静默丢弃，防止 DOM 插入激活最小化窗口。
 *
 * ElMessageBox 的 confirm/prompt 在被阻止时返回 rejected Promise，
 * 保持与用户点击"取消"一致的语义，调用方的 catch 分支正常处理。
 */

import { ElMessage as _ElMessage, ElMessageBox as _ElMessageBox } from 'element-plus'

let _isRestoring = false
let _restoreTimer = null

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !_isRestoring) {
    _isRestoring = true
    if (_restoreTimer) clearTimeout(_restoreTimer)
    _restoreTimer = setTimeout(() => {
      _isRestoring = false
    }, 2000)
  }
})

function _shouldBlock() {
  return document.hidden || _isRestoring
}

// ---- ElMessage 安全包装 ----

const safeElMessage = Object.assign(function(options) {
  if (_shouldBlock()) return
  return _ElMessage(options)
}, _ElMessage)

safeElMessage.closeAll = _ElMessage.closeAll
safeElMessage.success = (...args) => { if (_shouldBlock()) return; return _ElMessage.success(...args) }
safeElMessage.error = (...args) => { if (_shouldBlock()) return; return _ElMessage.error(...args) }
safeElMessage.warning = (...args) => { if (_shouldBlock()) return; return _ElMessage.warning(...args) }
safeElMessage.info = (...args) => { if (_shouldBlock()) return; return _ElMessage.info(...args) }
safeElMessage.loading = (...args) => { if (_shouldBlock()) return; return _ElMessage.loading(...args) }

// ---- ElMessageBox 安全包装 ----
// confirm/prompt 被阻止时 reject，模拟用户点击"取消"
// alert 被阻止时 resolve，模拟用户点击"确定"

const safeElMessageBox = Object.assign({}, _ElMessageBox)

safeElMessageBox.alert = (...args) => {
  if (_shouldBlock()) return Promise.resolve()
  return _ElMessageBox.alert(...args)
}

safeElMessageBox.confirm = (...args) => {
  if (_shouldBlock()) return Promise.reject(new Error('页面隐藏时阻止弹窗'))
  return _ElMessageBox.confirm(...args)
}

safeElMessageBox.prompt = (...args) => {
  if (_shouldBlock()) return Promise.reject(new Error('页面隐藏时阻止弹窗'))
  return _ElMessageBox.prompt(...args)
}

export { safeElMessage as ElMessage, safeElMessageBox as ElMessageBox }