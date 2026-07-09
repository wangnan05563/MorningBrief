/**
 * {module} Pinia Store
 * 
 * 使用 Composition API 风格的 defineStore。
 * State 通过 ref/reactive 管理，Actions 通过 async 函数实现。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { XxxItem, XxxCreate, XxxUpdate } from '@/types'
import * as api from '@/api/{module}'

export const useXxxStore = defineStore('{module}', () => {
  // ==================== State ====================
  
  /** 列表数据 */
  const list = ref<XxxItem[]>([])
  
  /** 当前选中的 {entity} */
  const currentItem = ref<XxxItem | null>(null)
  
  /** 加载状态 */
  const loading = ref(false)
  
  /** 分页信息 */
  const pagination = ref({
    current: 1,
    pageSize: 20,
    total: 0,
  })
  
  /** 筛选条件 */
  const filters = ref({
    category: '',
    status: '',
  })

  // ==================== Getters ====================
  
  /** 是否有更多数据 */
  const hasMore = computed(() => {
    return pagination.value.current * pagination.value.pageSize < pagination.value.total
  })

  /** 当前页数据 */
  const currentPageData = computed(() => list.value)

  // ==================== Actions ====================
  
  /**
   * 获取列表（分页 + 筛选）
   * @param resetPage - 是否重置到第一页
   */
  async function fetchList(resetPage = false) {
    if (resetPage) {
      pagination.value.current = 1
    }
    
    loading.value = true
    try {
      const res = await api.getXxxList({
        page: pagination.value.current,
        page_size: pagination.value.pageSize,
        ...filters.value,
      })
      list.value = res.data.items
      pagination.value.total = res.data.total
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取详情
   * @param id - {entity} ID
   */
  async function fetchDetail(id: number) {
    loading.value = true
    try {
      const res = await api.getXxxDetail(id)
      currentItem.value = res.data
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建 {entity}
   * @param data - 创建数据
   */
  async function createItem(data: XxxCreate) {
    const result = await api.createXxx(data)
    // 创建成功后刷新列表
    await fetchList(true)
    return result
  }

  /**
   * 更新 {entity}
   * @param id - {entity} ID
   * @param data - 更新数据
   */
  async function updateItem(id: number, data: XxxUpdate) {
    const result = await api.updateXxx(id, data)
    // 更新成功后刷新当前页
    await fetchList()
    return result
  }

  /**
   * 删除 {entity}
   * @param id - {entity} ID
   */
  async function deleteItem(id: number) {
    await api.deleteXxx(id)
    // 删除后刷新列表，如果当前页为空则退回上一页
    await fetchList()
    if (list.value.length === 0 && pagination.value.current > 1) {
      pagination.value.current -= 1
      await fetchList()
    }
  }

  /**
   * 设置筛选条件
   * @param newFilters - 新的筛选条件
   */
  function setFilters(newFilters: Partial<typeof filters.value>) {
    filters.value = { ...filters.value, ...newFilters }
    // 筛选条件变化时重置到第一页
    pagination.value.current = 1
    await fetchList()
  }

  /**
   * 重置分页
   */
  function resetPagination() {
    pagination.value.current = 1
    pagination.value.pageSize = 20
  }

  /**
   * 清空当前选中
   */
  function clearCurrent() {
    currentItem.value = null
  }

  return {
    // State
    list,
    currentItem,
    loading,
    pagination,
    filters,
    
    // Getters
    hasMore,
    currentPageData,
    
    // Actions
    fetchList,
    fetchDetail,
    createItem,
    updateItem,
    deleteItem,
    setFilters,
    resetPagination,
    clearCurrent,
  }
})
