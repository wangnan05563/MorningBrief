/**
 * 素材库管理页专用接口（T00775）
 *
 * 为什么单独成文件：`api/materials.js` 正被另一并发改动整体重写（工作区未提交），
 * 把新增调用写进去会让本次提交裹挟他人改动。待其合入后，本模块可直接并入
 * `api/materials.js`（两者同属 /admin/api/v1/materials 前缀）。
 */
import api from '../api'

/** 按书聚合（GET /materials/aggregate）：一行一本书，聚合键 = 素材来源（书名） */
export const aggregateMaterials = (params) => api.get('/materials/aggregate', { params })
