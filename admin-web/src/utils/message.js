/**
 * ElMessage 安全包装器：防止最小化/隐藏时弹窗激活浏览器窗口
 * 
 * 核心策略：在所有 ElMessage 调用入口处拦截，
 * 只要页面不可见或正在恢复，就静默丢弃。
 */

import { ElMessage as _ElMessage } from 'element-plus'

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

export { safeElMessage as ElMessage }