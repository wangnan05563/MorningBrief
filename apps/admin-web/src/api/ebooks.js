/**
 * 找书工具 API 封装（T00601 / T00603）
 *
 * 对应后端 /admin/api/v1/ebooks/*（已在 main.py 挂载 b_ebooks_router），需管理员权限。
 *
 * 定位：自动化「找书」——在书源仓库的 1000 个分类清单里检索书名/作者并给出下载链接；
 * 「取件」由人工完成（链接为城通网盘，无直链），下载 EPUB/DOCX 后到「素材录入」上传入库。
 */
import api from '../api'

// 书源全部分类（用于下拉筛选）
export const getEbookCategories = (force = false) =>
  api.get('/ebooks/categories', { params: { force } })

// 按关键词检索书名/作者；category 为空则走全量索引（索引未就绪时返回 428 并触发构建）
export const searchEbooks = ({ keyword, category = '', limit = 20 }) =>
  api.get('/ebooks/search', {
    params: { keyword, ...(category ? { category } : {}), limit },
  })

// 书源索引状态（就绪 / 构建进度）
export const getEbookIndexStatus = () => api.get('/ebooks/index/status')

// 重建书源索引（后台执行，约 2-5 分钟；进度走 status 轮询）
export const rebuildEbookIndex = () => api.post('/ebooks/index/rebuild')
