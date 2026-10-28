/**
 * T02544 切片 2：诚实性/错误态 4 条（A18 / E15 / F5 / M13）
 *
 * 每条都按评审报告的「修订后修法」钉，而不是原建议：
 * - A18：读取失败不许改写成「内置清单」，只能标未知；
 * - E15：script/review 面板补手动刷新（错误态已有 ListLoadError）；
 * - F5：切预设/保存成功后清掉上一次连接测试结论；
 * - M13：计算器只带入两个字段，不得顺手清掉其他未保存修改（不清草稿、只补提示）。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const SRC = '../../src/'

const voiceSync = read(`${SRC}components/VoiceSyncButton.vue`)
const workflowDetail = read(`${SRC}views/workflow/WorkflowDetail.vue`)
const aiConfig = read(`${SRC}views/ai/AIConfig.vue`)

function sliceBetween(text, startMark, endMark) {
  const start = text.indexOf(startMark)
  assert.ok(start >= 0, `缺少定位标记：${startMark}`)
  const end = text.indexOf(endMark, start + startMark.length)
  assert.ok(end > start, `缺少结束标记：${endMark}`)
  return text.slice(start, end)
}

test('A18：meta 读取失败标记未知，不得改写成「尚未同步/内置清单」', () => {
  assert.match(voiceSync, /const metaError = ref\(''\)/)
  assert.match(voiceSync, /同步状态未知：/)
  const loadMeta = sliceBetween(voiceSync, 'async function loadMeta', 'async function onSync')
  const catchBlock = loadMeta.slice(loadMeta.indexOf('} catch (e) {'))
  assert.match(catchBlock, /metaError\.value = /, '失败必须落到 metaError')
  assert.doesNotMatch(catchBlock, /is_custom:\s*false/, '失败不得冒充内置态')
  // 未知态下不显示「官方同步」角标与重置入口，避免基于未证实状态操作
  assert.match(voiceSync, /meta\.is_custom && !props\.disabled && !metaError/)
  assert.match(voiceSync, /meta\.is_custom && !syncing && !metaError/)
})

test('E15：稿件与审核记录面板都能手动刷新', () => {
  const rewritePanel = sliceBetween(workflowDetail, '<el-collapse-item name="rewrite">', '<el-collapse-item name="tts">')
  assert.match(rewritePanel, /label="刷新"/)
  assert.match(rewritePanel, /@click="loadScript"/)

  // review 是最后一个折叠面板，用顶层 </el-collapse> 收口
  const reviewPanel = sliceBetween(workflowDetail, '<el-collapse-item name="review">', '      </el-collapse>')
  assert.match(reviewPanel, /label="刷新"/)
  assert.match(reviewPanel, /@click="loadReview"/)
})

test('F5：应用预设与保存成功后清空 LLM 测试结论', () => {
  const applyPreset = sliceBetween(aiConfig, 'function applyPreset(key)', '// 保存配置')
  assert.match(applyPreset, /llmTestResult\.value = null/)

  const handleSave = sliceBetween(aiConfig, 'async function handleSave()', '// 图片服务连接测试')
  const successIdx = handleSave.indexOf("ElMessage.success('配置已保存并热更新')")
  assert.ok(successIdx >= 0, '保存成功提示缺失')
  assert.match(handleSave.slice(successIdx), /llmTestResult\.value = null/, '保存成功后必须清测试标签')
})

test('M13：计算器带入不清草稿，并明确告知未保存修改仍保留', () => {
  const applyCalc = sliceBetween(aiConfig, 'function applyCalculatorParams()', 'onMounted(async () => {')
  assert.match(applyCalc, /hasAnyDraft\(\)/)
  assert.match(applyCalc, /其余未保存修改仍保留为草稿/)
  assert.doesNotMatch(applyCalc, /commitDraft\(\)/, '带入参数不得提交/清空草稿')
})
