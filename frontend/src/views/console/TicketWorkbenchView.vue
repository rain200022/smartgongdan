<script setup lang="ts">
import {
  BookOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  HistoryOutlined,
  ReloadOutlined,
  RobotOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { APIError } from '@/api/client'
import {
  analyzeTicket,
  claimTicket,
  releaseTicket,
  getTicketEvents,
  closeTicket,
  confirmClassification,
  getClassificationTree,
  getJudgments,
  getLatestAnalysis,
  getLatestSolution,
  getSimilarResults,
  getTicket,
  generateSolution,
  reviewSolution,
  updateTicketStatus,
} from '@/api/tickets'
import type { TicketEvent } from '@/api/tickets'
import type {
  ClassificationTree,
  Judgment,
  RejectionCategory,
  SimilarResult,
  Ticket,
  TicketAIAnalysis,
  TicketAISolution,
  TicketPriority,
} from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { readDraft, removeDraft, saveDraft } from '@/stores/drafts'
import { session } from '@/stores/session'

interface HandlingForm {
  category: string | undefined
  subcategory: string | undefined
  priority: TicketPriority
  resolution: string
}

interface WorkbenchDraft {
  baseline?: HandlingForm
  handling: HandlingForm
  solutionId: number | null
  solutionDraft: string
  rejectionReason: string
  rejectionCategory: RejectionCategory | undefined
}

const route = useRoute()
const loading = ref(true)
const actionLoading = ref('')
const errorMessage = ref('')
const conflictMessage = ref('')
const previousResolution = ref('')
const events = ref<TicketEvent[]>([])
const eventError = ref('')
const eventsLoading = ref(false)
const moreEvents = ref(false)
const ticket = ref<Ticket | null>(null)
const analysis = ref<TicketAIAnalysis | null>(null)
const solution = ref<TicketAISolution | null>(null)
const judgments = ref<Judgment[]>([])
const classificationTree = ref<ClassificationTree>({})
const similarResults = ref<SimilarResult[]>([])
const similarLoading = ref(false)
const similarError = ref('')
const searchModel = ref('')
const solutionDraft = ref('')
const rejectionReason = ref('')
const rejectionCategory = ref<RejectionCategory | undefined>()
const handling = reactive<HandlingForm>({
  category: undefined as string | undefined,
  subcategory: undefined as string | undefined,
  priority: 'P3' as TicketPriority,
  resolution: '',
})

const ticketId = computed(() => Number(route.params.ticketId))
const categories = computed(() => Object.keys(classificationTree.value))
const subcategories = computed(() =>
  handling.category ? (classificationTree.value[handling.category] ?? []) : [],
)
const isClosed = computed(() => ticket.value?.status === 'closed')
const assignedToOther = computed(() => ticket.value?.assigned_engineer_id != null
  && ticket.value.assigned_engineer_id !== session.state.user?.id
  && session.state.user?.role !== 'ADMIN')
const readOnly = computed(() => isClosed.value || assignedToOther.value || Boolean(conflictMessage.value))
const closeConfirming = ref(false)
const busy = computed(() => Boolean(actionLoading.value) || closeConfirming.value)
const draftOwner = session.state.user!.id
const draftKey = computed(() => `workbench:${ticketId.value}`)
const baseline = ref('')
const draftReady = ref(false)
let loadVersion = 0
let similarVersion = 0
let eventsVersion = 0
const dirty = computed(() => draftReady.value && !isClosed.value && JSON.stringify(draftSnapshot()) !== baseline.value)
const backPath = computed(() => {
  const path = route.query.returnTo
  return typeof path === 'string' && /^\/console\/tickets(?:\?|$)/.test(path) ? path : '/console/tickets'
})
useUnsavedChanges(dirty, busy)
onBeforeUnmount(() => {
  loadVersion += 1
  similarVersion += 1
})
watch([handling, solutionDraft, rejectionReason, rejectionCategory, baseline], () => {
  if (!draftReady.value || (session.state.user?.id !== draftOwner && !session.state.expired)) return
  if (dirty.value) saveWorkbenchDraft()
  else removeDraft(draftOwner, draftKey.value)
}, { deep: true, flush: 'sync' })
const solutionIsStale = computed(
  () =>
    Boolean(solution.value && analysis.value) &&
    new Date(solution.value!.created_at).getTime() < new Date(analysis.value!.created_at).getTime(),
)

watch(
  ticketId,
  async (value) => {
    await loadWorkbench(value)
  },
  { immediate: true },
)

function draftSnapshot(): WorkbenchDraft {
  return {
    handling: { ...handling },
    solutionId: solution.value?.id ?? null,
    solutionDraft: solutionDraft.value,
    rejectionReason: rejectionReason.value,
    rejectionCategory: rejectionCategory.value,
  }
}

function initializeDraft(): void {
  baseline.value = JSON.stringify(draftSnapshot())
  const saved = readDraft<WorkbenchDraft>(draftOwner, draftKey.value)
  previousResolution.value = ''
  if (isClosed.value) {
    if (saved && saved.handling.resolution !== handling.resolution) {
      previousResolution.value = saved.handling.resolution
    }
    draftReady.value = true
    return
  }
  if (saved) {
    const original = saved.baseline
    if (!original || saved.handling.category !== original.category || saved.handling.subcategory !== original.subcategory) {
      handling.category = saved.handling.category
      handling.subcategory = saved.handling.subcategory
    }
    if (!original || saved.handling.priority !== original.priority) handling.priority = saved.handling.priority
    if (!original || saved.handling.resolution !== original.resolution) handling.resolution = saved.handling.resolution
    if (saved.solutionId === (solution.value?.id ?? null)) {
      solutionDraft.value = saved.solutionDraft
      rejectionReason.value = saved.rejectionReason
      rejectionCategory.value = saved.rejectionCategory
    }
  }
  draftReady.value = true
}

function saveWorkbenchDraft(): void {
  const original = baseline.value ? (JSON.parse(baseline.value) as WorkbenchDraft).handling : undefined
  saveDraft(draftOwner, draftKey.value, { ...draftSnapshot(), baseline: original })
}

async function optionalLatestAnalysis(id: number): Promise<TicketAIAnalysis | null> {
  try {
    return await getLatestAnalysis(id)
  } catch (error) {
    if (error instanceof APIError && error.status === 404) return null
    throw error
  }
}

async function optionalLatestSolution(id: number): Promise<TicketAISolution | null> {
  try {
    return await getLatestSolution(id)
  } catch (error) {
    if (error instanceof APIError && error.status === 404) return null
    throw error
  }
}

function setSolutionDraft(): void {
  if (!solution.value) {
    solutionDraft.value = ''
    rejectionReason.value = ''
    rejectionCategory.value = undefined
    return
  }
  solutionDraft.value =
    solution.value.review?.engineer_solution ?? solution.value.steps.join('\n')
  rejectionReason.value = solution.value.review?.rejection_reason ?? ''
  rejectionCategory.value = solution.value.review?.rejection_category ?? undefined
}

function validPair(value: string | null | undefined): [string, string] | null {
  if (!value) return null
  const [category, subcategory] = value.split('/', 2)
  if (!category || !subcategory) return null
  if (!classificationTree.value[category]?.includes(subcategory)) return null
  return [category, subcategory]
}

function setHandlingDefaults(preserveEdits = false): void {
  if (!ticket.value) return
  const pair =
    validPair(ticket.value.final_category) ??
    (analysis.value ? validPair(`${analysis.value.category}/${analysis.value.subcategory}`) : null) ??
    validPair(ticket.value.user_category)
  const defaults: HandlingForm = {
    category: pair?.[0],
    subcategory: pair?.[1],
    priority: ticket.value.final_priority ?? ticket.value.ai_priority ?? 'P3',
    resolution: ticket.value.resolution ?? '',
  }
  const previous = baseline.value ? (JSON.parse(baseline.value) as WorkbenchDraft) : null
  if (!preserveEdits || !previous) {
    Object.assign(handling, defaults)
  } else {
    if (handling.category === previous.handling.category && handling.subcategory === previous.handling.subcategory) {
      handling.category = defaults.category
      handling.subcategory = defaults.subcategory
    }
    if (handling.priority === previous.handling.priority) handling.priority = defaults.priority
    if (handling.resolution === previous.handling.resolution) handling.resolution = defaults.resolution
    baseline.value = JSON.stringify({ ...previous, handling: defaults })
  }
}

async function loadWorkbench(id: number): Promise<void> {
  const version = ++loadVersion
  similarVersion += 1
  draftReady.value = false
  actionLoading.value = ''
  loading.value = true
  errorMessage.value = ''
  conflictMessage.value = ''
  events.value = []
  eventError.value = ''
  ticket.value = null
  analysis.value = null
  solution.value = null
  judgments.value = []
  similarResults.value = []
  similarError.value = ''
  if (!Number.isInteger(id) || id <= 0) {
    errorMessage.value = '工单编号无效，请在顶部输入正确编号。'
    loading.value = false
    return
  }
  try {
    const [ticketData, tree, analysisData, solutionData, judgmentData] = await Promise.all([
      getTicket(id),
      getClassificationTree(),
      optionalLatestAnalysis(id),
      optionalLatestSolution(id),
      getJudgments(id),
    ])
    if (version !== loadVersion) return
    ticket.value = ticketData
    classificationTree.value = tree
    analysis.value = analysisData
    solution.value = solutionData
    judgments.value = judgmentData
    setHandlingDefaults()
    setSolutionDraft()
    initializeDraft()
    void loadEvents()
    void loadSimilarResults(id)
  } catch (error) {
    if (version !== loadVersion) return
    errorMessage.value = error instanceof Error ? error.message : '工单加载失败'
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

async function loadSimilarResults(id = ticketId.value): Promise<void> {
  const version = ++similarVersion
  similarLoading.value = true
  similarError.value = ''
  try {
    const result = await getSimilarResults(id)
    if (version !== similarVersion || id !== ticketId.value) return
    similarResults.value = result.items
    searchModel.value = result.query_model
  } catch (error) {
    if (version !== similarVersion || id !== ticketId.value) return
    similarError.value = error instanceof Error ? error.message : '相似内容检索失败'
  } finally {
    if (version === similarVersion) similarLoading.value = false
  }
}

function resetSubcategory(): void {
  handling.subcategory = undefined
}

async function runAction(name: string, action: (id: number, isCurrent: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || readOnly.value || loading.value || !ticket.value) return
  const id = ticketId.value
  const revision = ticket.value.version
  const version = loadVersion
  const isCurrent = (): boolean => version === loadVersion && session.state.user?.id === draftOwner
  actionLoading.value = name
  try {
    await action(id, isCurrent)
    if (isCurrent() && ticket.value) {
      // Never silently adopt a version produced by another request.
      if (ticket.value.version > revision + 1) {
        conflictMessage.value = '处理期间工单再次更新，请加载最新记录并核对草稿。'
      } else {
        ticket.value.version = revision + 1
      }
      void loadEvents()
    }
  } catch (error) {
    if (isCurrent()) {
      if (error instanceof APIError && (error.status === 409 || error.status === 403)) {
        conflictMessage.value = error.message
      }
      message.error(error instanceof Error ? error.message : '操作失败，请重试')
    }
  } finally {
    if (version === loadVersion) actionLoading.value = ''
  }
}

async function loadEvents(append = false): Promise<void> {
  const version = loadVersion
  const sequence = ++eventsVersion
  eventsLoading.value = true
  eventError.value = ''
  try {
    const result = await getTicketEvents(ticketId.value, append ? events.value.length : 0)
    if (version !== loadVersion || sequence !== eventsVersion) return
    events.value = append ? [...events.value, ...result] : result
    moreEvents.value = result.length === 100
  } catch (error) {
    if (version === loadVersion && sequence === eventsVersion) eventError.value = error instanceof Error ? error.message : '操作记录加载失败'
  } finally {
    if (version === loadVersion && sequence === eventsVersion) eventsLoading.value = false
  }
}

const actionLabels: Record<string, string> = {
  claimed: '认领工单', released: '释放工单', updated: '更新工单',
  analyzed: '完成 AI 分析', classification_confirmed: '确认分类',
  solution_generated: '生成 AI 建议', solution_reviewed: '审核 AI 建议', closed: '关闭工单',
}

async function claim(): Promise<void> {
  await runAction('claim', async (id, isCurrent) => {
    const result = await claimTicket(id, ticket.value!.version)
    if (isCurrent()) ticket.value = result
  })
}

async function release(): Promise<void> {
  const version = loadVersion
  Modal.confirm({
    title: '确认释放工单？', content: '释放后其他工程师可以认领，当前处理状态保持不变。',
    okText: '确认释放', cancelText: '继续处理',
    onOk: async () => {
      if (version !== loadVersion) return
      await runAction('release', async (id, isCurrent) => {
        const result = await releaseTicket(id, ticket.value!.version)
        if (isCurrent()) ticket.value = result
      })
    },
  })
}

async function reloadKeepingDraft(): Promise<void> {
  if (dirty.value) saveWorkbenchDraft()
  await loadWorkbench(ticketId.value)
}

async function startProcessing(): Promise<void> {
  await runAction('start', async (id, isCurrent) => {
    const result = await updateTicketStatus(id, 'in_progress', ticket.value!.version)
    if (!isCurrent()) return
    ticket.value = result
    message.success('工单已进入处理状态')
  })
}

async function analyze(): Promise<void> {
  await runAction('analyze', async (id, isCurrent) => {
    const analysisData = await analyzeTicket(id, ticket.value!.version)
    if (!isCurrent()) return
    analysis.value = analysisData
    const [ticketData, judgmentData] = await Promise.all([
      getTicket(id),
      getJudgments(id),
    ])
    if (!isCurrent()) return
    ticket.value = ticketData
    judgments.value = judgmentData
    setHandlingDefaults(true)
    await loadSimilarResults(id)
    if (isCurrent()) message.success('AI 分析已更新，人工填写的内容已保留')
  })
}

async function createSolution(): Promise<void> {
  if (!analysis.value) {
    message.warning('请先完成 AI 工单分析')
    return
  }
  await runAction('solution', async (id, isCurrent) => {
    const result = await generateSolution(id, ticket.value!.version)
    if (!isCurrent()) return
    solution.value = result
    setSolutionDraft()
    message.success(
      solution.value.need_human
        ? '证据不足，已标记为需要人工判断'
        : 'AI 处理建议已生成，请审核后使用',
    )
  })
}

async function adoptSolution(): Promise<void> {
  if (!solution.value || !solutionDraft.value.trim() || solutionIsStale.value) {
    message.warning('请先填写可执行的解决方案')
    return
  }
  await runAction('adopt-solution', async (id, isCurrent) => {
    const draft = solutionDraft.value.trim()
    const result = await reviewSolution(id, solution.value!.id, {
      decision: 'ADOPTED',
      engineer_solution: draft,
    }, ticket.value!.version)
    if (!isCurrent()) return
    solution.value = result
    handling.resolution = draft
    message.success('已采纳并填入最终解决方案，确认执行结果后可关闭工单')
  })
}

async function rejectSolution(): Promise<void> {
  if (!solution.value) return
  if (!rejectionCategory.value) {
    message.warning('请选择不采纳原因类型')
    return
  }
  if (!rejectionReason.value.trim()) {
    message.warning('请简要填写拒绝原因，便于后续评估')
    return
  }
  await runAction('reject-solution', async (id, isCurrent) => {
    const result = await reviewSolution(id, solution.value!.id, {
      decision: 'REJECTED',
      rejection_category: rejectionCategory.value,
      rejection_reason: rejectionReason.value.trim(),
    }, ticket.value!.version)
    if (!isCurrent()) return
    solution.value = result
    message.success('已记录拒绝原因，本条建议不会作为最终方案使用')
  })
}

async function confirm(): Promise<void> {
  if (!handling.category || !handling.subcategory) {
    message.warning('请先选择完整的最终分类')
    return
  }
  await runAction('confirm', async (id, isCurrent) => {
    const result = await confirmClassification(
      id,
      handling.category as string,
      handling.subcategory as string,
      ticket.value!.version,
    )
    if (!isCurrent()) return
    const [ticketData, judgmentData] = await Promise.all([getTicket(id), getJudgments(id)])
    if (!isCurrent()) return
    ticket.value = ticketData
    judgments.value = judgmentData
    if (result.evaluation?.agreement) {
      message.success('分类已确认，与 AI 判断一致')
    } else if (result.evaluation) {
      message.success('分类已确认，差异已记录用于评估')
    } else {
      message.success('分类已确认')
    }
  })
}

async function closeCurrentTicket(): Promise<void> {
  if (busy.value || readOnly.value || loading.value) return
  if (!handling.category || !handling.subcategory) {
    message.warning('关闭前需要确认最终分类')
    return
  }
  if (!handling.resolution.trim()) {
    message.warning('请填写最终解决方案')
    return
  }
  const version = loadVersion
  closeConfirming.value = true
  const approved = await new Promise<boolean>((resolve) => {
    Modal.confirm({
      title: '确认关闭工单？',
      content: `最终分类：${handling.category}/${handling.subcategory}，优先级：${handling.priority}。请确认问题已解决；关闭后记录只读。`,
      okText: '确认关闭',
      cancelText: '继续处理',
      onOk: () => { resolve(true) },
      onCancel: () => { resolve(false) },
    })
  })
  closeConfirming.value = false
  if (!approved || version !== loadVersion) return
  await runAction('close', async (id, isCurrent) => {
    const result = await closeTicket(id, {
      final_category: `${handling.category}/${handling.subcategory}`,
      final_priority: handling.priority,
      resolution: handling.resolution.trim(),
    }, ticket.value!.version)
    removeDraft(draftOwner, `workbench:${id}`)
    if (!isCurrent()) return
    ticket.value = result
    draftReady.value = false
    message.success('工单已关闭')
  })
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function judgeLabel(type: Judgment['judge_type']): string {
  return { USER: '用户判断', AI: 'AI 判断', ENGINEER: '工程师确认' }[type]
}
</script>

<template>
  <a-skeleton v-if="loading" active :paragraph="{ rows: 12 }" />

  <a-result v-else-if="errorMessage" status="404" title="无法打开工单" :sub-title="errorMessage">
    <template #extra>
      <p class="result-hint">可使用页面顶部搜索框输入其他工单编号。</p>
    </template>
  </a-result>

  <article v-else-if="ticket" class="workbench">
    <router-link :to="backPath">返回工单队列</router-link>
    <a-alert v-if="conflictMessage" type="warning" show-icon :message="conflictMessage"
      description="未提交草稿仍保留；加载后请核对最新处理记录，再决定是否提交。" />
    <a-alert v-if="assignedToOther" type="info" show-icon message="该工单已由其他工程师认领，当前为只读视图。" />
    <div class="assignment-toolbar">
      <span>负责人：{{ ticket.assigned_engineer_name || '未认领' }} · 版本 {{ ticket.version }}</span>
      <a-button v-if="!ticket.assigned_engineer_id && !isClosed" :disabled="busy || readOnly" @click="claim">认领工单</a-button>
      <a-button v-else-if="!isClosed && !assignedToOther" :disabled="busy || readOnly" @click="release">释放工单</a-button>
      <a-button :disabled="busy" @click="reloadKeepingDraft">加载最新记录</a-button>
    </div>
    <header class="ticket-heading">
      <div>
        <div class="ticket-kicker">
          <span>INC-{{ String(ticket.id).padStart(4, '0') }}</span>
          <StatusTag :value="ticket.status" />
          <StatusTag v-if="ticket.final_priority ?? ticket.ai_priority" :value="ticket.final_priority ?? ticket.ai_priority!" />
        </div>
        <h1>{{ ticket.title }}</h1>
        <p>创建于 {{ formatDate(ticket.created_at) }} · 最近更新 {{ formatDate(ticket.updated_at) }}</p>
      </div>
      <a-button
        v-if="ticket.status === 'open'"
        :disabled="busy || readOnly"
        :loading="actionLoading === 'start'"
        @click="startProcessing"
      >
        开始处理
      </a-button>
    </header>

    <a-alert
      v-if="isClosed"
      class="closed-alert"
      type="success"
      show-icon
      message="此工单已经关闭，处理记录保持只读。"
    />

    <div class="workbench-grid">
      <div class="ticket-context">
        <section class="content-panel">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">用户提交</p>
              <h2>原始问题</h2>
            </div>
            <span v-if="ticket.user_category" class="plain-label">{{ ticket.user_category }}</span>
          </div>
          <p class="ticket-description">{{ ticket.description }}</p>
        </section>

        <section class="content-panel ai-panel">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow panel-eyebrow--ai"><RobotOutlined /> AI 分析</p>
              <h2>结构化理解</h2>
            </div>
            <a-button
              v-if="!isClosed"
              size="small"
              :disabled="busy || readOnly"
              :loading="actionLoading === 'analyze'"
              @click="analyze"
            >
              {{ analysis ? '重新分析' : '开始分析' }}
            </a-button>
          </div>

          <template v-if="analysis">
            <p class="ai-summary">{{ analysis.summary }}</p>
            <dl class="analysis-grid">
              <div>
                <dt>建议分类</dt>
                <dd>{{ analysis.category }} / {{ analysis.subcategory }}</dd>
              </div>
              <div>
                <dt>置信度</dt>
                <dd>{{ Math.round(analysis.confidence * 100) }}%</dd>
              </div>
              <div>
                <dt>设备</dt>
                <dd>{{ analysis.device || '未识别' }}</dd>
              </div>
              <div>
                <dt>问题症状</dt>
                <dd>{{ analysis.symptom || '未识别' }}</dd>
              </div>
              <div class="analysis-grid__wide">
                <dt>错误信息</dt>
                <dd>{{ analysis.error_message || '未识别' }}</dd>
              </div>
              <div class="analysis-grid__wide">
                <dt>用户已尝试</dt>
                <dd>
                  <span v-if="analysis.attempted_actions.length">
                    {{ analysis.attempted_actions.join('、') }}
                  </span>
                  <span v-else>未识别</span>
                </dd>
              </div>
            </dl>
            <section
              v-if="analysis.calculated_priority"
              class="priority-assessment"
              aria-labelledby="priority-assessment-title"
            >
              <div class="priority-assessment__heading">
                <div>
                  <span id="priority-assessment-title">规则优先级</span>
                  <p>AI 提取事实，系统规则计算等级</p>
                </div>
                <div class="priority-result">
                  <StatusTag :value="analysis.calculated_priority" />
                  <strong>{{ analysis.priority_score ?? '—' }} 分</strong>
                </div>
              </div>
              <dl class="priority-factors">
                <div>
                  <dt>影响程度 · 50%</dt>
                  <dd>
                    <span>{{ analysis.impact }}</span>
                    <strong>{{ analysis.impact_score ?? '—' }}</strong>
                  </dd>
                </div>
                <div>
                  <dt>紧急度 · 30%</dt>
                  <dd>
                    <span>{{ analysis.urgency }}</span>
                    <strong>{{ analysis.urgency_score ?? '—' }}</strong>
                  </dd>
                </div>
                <div>
                  <dt>影响范围 · 20%</dt>
                  <dd>
                    <span>{{ analysis.affected_scope }}</span>
                    <strong>{{ analysis.scope_score ?? '—' }}</strong>
                  </dd>
                </div>
              </dl>
              <p class="priority-thresholds">≥80 P1 · ≥60 P2 · ≥30 P3 · &lt;30 P4</p>
            </section>
            <a-alert
              v-else
              class="legacy-priority-note"
              type="info"
              show-icon
              :message="
                isClosed
                  ? '该分析产生于优先级规则上线前；已关闭工单保持不可变。'
                  : '该历史分析尚未执行规则优先级评估，可重新分析生成。'
              "
            />
            <p class="model-note">由 {{ analysis.model_name }} 于 {{ formatDate(analysis.created_at) }} 生成</p>
          </template>
          <a-empty v-else :image="undefined" description="尚未执行 AI 分析">
            <template #image><RobotOutlined class="empty-ai-icon" /></template>
          </a-empty>
        </section>

        <section class="content-panel solution-panel" aria-labelledby="solution-title">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow panel-eyebrow--ai"><BulbOutlined /> AI 辅助</p>
              <h2 id="solution-title">处理建议</h2>
            </div>
            <a-button
              v-if="!isClosed"
              size="small"
              :disabled="!analysis || busy || readOnly"
              :loading="actionLoading === 'solution'"
              @click="createSolution"
            >
              {{ solution ? '重新生成' : '生成建议' }}
            </a-button>
          </div>

          <a-empty
            v-if="!solution"
            :description="analysis ? '尚未生成处理建议' : '完成 AI 分析后才能生成处理建议'"
          />
          <template v-else>
            <a-alert
              v-if="solutionIsStale"
              class="solution-alert"
              type="warning"
              show-icon
              message="AI 分析已更新，这条建议已经过期，请重新生成后再审核。"
            />
            <a-alert
              v-else-if="solution.need_human"
              class="solution-alert"
              type="warning"
              show-icon
              message="当前证据不足或风险较高，需要工程师独立判断。"
            />

            <div class="solution-diagnosis">
              <span>初步诊断</span>
              <p>{{ solution.diagnosis }}</p>
            </div>

            <div v-if="solution.possible_causes.length" class="solution-block">
              <h3>可能原因</h3>
              <ul>
                <li v-for="cause in solution.possible_causes" :key="cause">{{ cause }}</li>
              </ul>
            </div>

            <div class="solution-block">
              <h3>建议步骤</h3>
              <ol v-if="solution.steps.length" class="solution-steps">
                <li v-for="step in solution.steps" :key="step">{{ step }}</li>
              </ol>
              <p v-else class="solution-empty">没有足够证据生成可执行步骤。</p>
            </div>

            <div class="solution-references">
              <span>引用依据</span>
              <div v-if="solution.referenced_cases.length">
                <span v-for="reference in solution.referenced_cases" :key="reference">
                  {{ reference }}
                </span>
              </div>
              <p v-else>无可引用证据</p>
            </div>

            <a-alert
              v-if="solution.review"
              class="solution-review-result"
              :type="solution.review.decision === 'ADOPTED' ? 'success' : 'info'"
              show-icon
              :message="solution.review.decision === 'ADOPTED' ? '工程师已采纳并编辑' : '工程师已拒绝此建议'"
              :description="
                solution.review.decision === 'ADOPTED'
                  ? solution.review.engineer_solution ?? undefined
                  : solution.review.rejection_reason ?? '未填写原因'
              "
            />

            <div v-else-if="!isClosed" class="solution-review">
              <label for="solution-draft">工程师方案草稿</label>
              <p>编辑后采纳会填入右侧最终解决方案，但不会自动执行或关闭工单。</p>
              <a-textarea
                id="solution-draft"
                v-model:value="solutionDraft"
                :disabled="solutionIsStale || busy || readOnly"
                :rows="5"
                placeholder="根据现场情况调整建议步骤"
              />
              <a-button
                type="primary"
                :disabled="solutionIsStale || busy || readOnly"
                :loading="actionLoading === 'adopt-solution'"
                @click="adoptSolution"
              >
                采纳并填入最终方案
              </a-button>

              <div class="solution-reject">
                <label for="rejection-reason">不采纳原因</label>
                <div>
                  <a-select
                    v-model:value="rejectionCategory"
                    :disabled="solutionIsStale || busy || readOnly"
                    placeholder="原因类型"
                    :options="[
                      { value: 'EVIDENCE_MISMATCH', label: '证据不匹配' },
                      { value: 'ALREADY_TRIED', label: '步骤已经尝试' },
                      { value: 'RISK_OR_INCOMPLETE', label: '风险或信息不足' },
                      { value: 'OTHER', label: '其他原因' },
                    ]"
                  />
                  <a-input
                    id="rejection-reason"
                    v-model:value="rejectionReason"
                    :disabled="solutionIsStale || busy || readOnly"
                    placeholder="例如：现场症状与引用案例不一致"
                    @press-enter="rejectSolution"
                  />
                  <a-button
                    danger
                    :disabled="solutionIsStale || busy || readOnly"
                    :loading="actionLoading === 'reject-solution'"
                    @click="rejectSolution"
                  >
                    拒绝建议
                  </a-button>
                </div>
              </div>
            </div>

            <p class="model-note">
              由 {{ solution.model_name }} 于 {{ formatDate(solution.created_at) }} 生成 · 仅供人工审核
            </p>
          </template>
        </section>

        <section class="content-panel" aria-labelledby="similar-title">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">检索辅助</p>
              <h2 id="similar-title">相似知识与历史案例</h2>
            </div>
            <a-button size="small" :loading="similarLoading" @click="loadSimilarResults()">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
          </div>
          <a-skeleton v-if="similarLoading && !similarResults.length" active :paragraph="{ rows: 4 }" />
          <a-alert
            v-else-if="similarError"
            type="warning"
            show-icon
            :message="similarError"
          />
          <a-empty v-else-if="!similarResults.length" description="暂无相似知识或历史案例" />
          <div v-else class="similar-list">
            <article v-for="item in similarResults" :key="`${item.source_type}:${item.source_id}`">
              <div class="similar-item__heading">
                <span class="similar-source">
                  <BookOutlined v-if="item.source_type === 'knowledge'" />
                  <HistoryOutlined v-else />
                  {{ item.source_type === 'knowledge' ? '知识' : '历史工单' }}
                </span>
                <span class="similar-score">综合匹配 {{ Math.round(item.combined_score * 100) }}%</span>
              </div>
              <div class="similar-item__title">
                <strong>{{ item.reference }} · {{ item.title }}</strong>
                <span>{{ item.category }} / {{ item.subcategory }}</span>
              </div>
              <p>{{ item.excerpt }}</p>
              <div v-if="item.resolution" class="similar-resolution">
                <span>历史解决结果</span>
                <p>{{ item.resolution }}</p>
              </div>
              <div class="match-reasons" aria-label="匹配方式">
                <span v-for="reason in item.match_reasons" :key="reason">{{ reason }}</span>
              </div>
            </article>
          </div>
          <p v-if="searchModel && similarResults.length" class="model-note">
            关键词与 {{ searchModel }} 向量结果合并去重 · Top {{ similarResults.length }}
          </p>
        </section>

        <section class="content-panel">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">审计记录</p>
              <h2>分类判断历史</h2>
            </div>
          </div>
          <a-empty v-if="!judgments.length" description="暂无判断记录" />
          <a-timeline v-else class="judgment-timeline">
            <a-timeline-item v-for="judgment in judgments" :key="judgment.id">
              <template #dot>
                <RobotOutlined v-if="judgment.judge_type === 'AI'" />
                <UserOutlined v-else-if="judgment.judge_type === 'ENGINEER'" />
                <ClockCircleOutlined v-else />
              </template>
              <div class="judgment-row">
                <div>
                  <strong>{{ judgeLabel(judgment.judge_type) }}</strong>
                  <span>{{ judgment.category }} / {{ judgment.subcategory }}</span>
                </div>
                <time>{{ formatDate(judgment.created_at) }}</time>
              </div>
            </a-timeline-item>
          </a-timeline>
        </section>
      </div>

      <aside class="handling-panel" aria-labelledby="handling-title">
        <a-alert v-if="previousResolution" type="warning" message="工单已被关闭，以下是您此前未提交的草稿，仅供复制核对。">
          <template #description><p class="previous-draft">{{ previousResolution }}</p></template>
        </a-alert>
        <div class="handling-panel__header">
          <div>
            <p class="panel-eyebrow">工程师处理</p>
            <h2 id="handling-title">最终处理结果</h2>
          </div>
          <CheckCircleOutlined v-if="isClosed" class="closed-icon" />
        </div>

        <p v-if="dirty" class="model-note" role="status">有未提交的修改，草稿仅保留在本标签页。关闭工单后才会保存最终方案。</p>
        <a-form :model="handling" layout="vertical">
          <div class="field-grid">
            <a-form-item label="最终分类" name="category" required>
              <a-select
                v-model:value="handling.category"
                aria-label="最终分类"
                :disabled="isClosed || busy || readOnly"
                placeholder="选择分类"
                :options="categories.map((value) => ({ value, label: value }))"
                @change="resetSubcategory"
              />
            </a-form-item>
            <a-form-item label="具体类型" name="subcategory" required>
              <a-select
                v-model:value="handling.subcategory"
                aria-label="具体类型"
                :disabled="isClosed || busy || !handling.category || readOnly"
                placeholder="选择类型"
                :options="subcategories.map((value) => ({ value, label: value }))"
              />
            </a-form-item>
          </div>

          <a-button
            v-if="!isClosed"
            block
            class="confirm-button"
            :disabled="busy || readOnly"
            :loading="actionLoading === 'confirm'"
            @click="confirm"
          >
            确认分类并记录 AI 一致性
          </a-button>

          <a-divider />

          <a-form-item label="最终优先级" name="priority" required>
            <a-radio-group v-model:value="handling.priority" :disabled="isClosed || busy || readOnly" button-style="solid">
              <a-radio-button value="P1">P1</a-radio-button>
              <a-radio-button value="P2">P2</a-radio-button>
              <a-radio-button value="P3">P3</a-radio-button>
              <a-radio-button value="P4">P4</a-radio-button>
            </a-radio-group>
          </a-form-item>

          <a-form-item label="最终解决方案" name="resolution" required>
            <a-textarea
              id="final-resolution"
              aria-label="最终解决方案"
              v-model:value="handling.resolution"
              :disabled="isClosed || busy || readOnly"
              :rows="7"
              placeholder="记录根因、执行步骤和验证结果，便于后续复用。"
            />
          </a-form-item>

          <a-button
            v-if="!isClosed"
            type="primary"
            block
            :disabled="busy || readOnly"
            :loading="actionLoading === 'close'"
            @click="closeCurrentTicket"
          >
            关闭工单
          </a-button>
          <div v-else class="closed-summary">
            <CheckCircleOutlined />
            已于 {{ ticket.resolved_at ? formatDate(ticket.resolved_at) : '—' }} 关闭
          </div>
        </a-form>
      </aside>
    </div>
    <section class="content-panel" aria-labelledby="events-title">
      <h2 id="events-title">操作记录</h2>
      <p class="model-note">从本次协作功能上线后开始记录，历史操作不补造操作人。</p>
      <a-alert v-if="eventError" type="error" :message="eventError">
        <template #action><a-button @click="loadEvents()">重试记录加载</a-button></template>
      </a-alert>
      <a-empty v-else-if="!events.length && !eventsLoading" description="暂无操作记录" />
      <ol class="event-list">
        <li v-for="event in events" :key="event.id">
          <time :datetime="event.created_at">{{ formatDate(event.created_at) }}</time>
          <span>{{ event.actor_name }} · {{ actionLabels[event.action] || event.action }} · 版本 {{ event.version }}</span>
        </li>
      </ol>
      <a-button v-if="moreEvents" :loading="eventsLoading" @click="loadEvents(true)">加载后续记录</a-button>
    </section>
  </article>
</template>

<style scoped>
.assignment-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin: var(--space-4) 0;
}
.event-list {
  padding-left: var(--space-5);
}
.event-list li {
  margin: var(--space-3) 0;
  overflow-wrap: anywhere;
}
.event-list time {
  margin-right: var(--space-3);
  color: var(--text-secondary);
}
.previous-draft { white-space: pre-wrap; overflow-wrap: anywhere; }
.workbench {
  width: min(100%, 1320px);
  margin: 0 auto;
}

.ticket-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-6);
  margin-bottom: var(--space-5);
}

.ticket-kicker {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.ticket-kicker > span:first-child {
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
}

.ticket-heading h1 {
  margin: 0 0 var(--space-1);
  font-size: 26px;
  line-height: 1.3;
  letter-spacing: -0.02em;
}

.ticket-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.closed-alert {
  margin-bottom: var(--space-4);
}

.workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(340px, 5fr);
  align-items: start;
  gap: var(--space-5);
}

.ticket-context {
  display: grid;
  gap: var(--space-4);
}

.content-panel,
.handling-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
  box-shadow: var(--shadow-subtle);
}

.content-panel {
  padding: var(--space-5);
}

.ai-panel {
  border-top: 3px solid var(--brand-ai);
}

.solution-panel {
  border-top: 3px solid var(--brand-primary);
}

.panel-heading,
.handling-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.panel-heading h2,
.handling-panel__header h2 {
  margin: 0;
  font-size: 17px;
}

.panel-eyebrow {
  margin: 0 0 var(--space-1);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel-eyebrow--ai {
  color: var(--brand-ai);
}

.plain-label {
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
  color: var(--text-secondary);
  font-size: 12px;
}

.ticket-description {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.8;
  white-space: pre-wrap;
}

.ai-summary {
  margin: 0 0 var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--brand-ai);
  background: #f7f5ff;
  line-height: 1.7;
}

.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--border-default);
}

.analysis-grid > div {
  min-width: 0;
  padding: var(--space-3);
  background: var(--surface-raised);
}

.analysis-grid__wide {
  grid-column: 1 / -1;
}

.analysis-grid dt {
  margin-bottom: var(--space-1);
  color: var(--text-muted);
  font-size: 12px;
}

.analysis-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.model-note {
  margin: var(--space-3) 0 0;
  color: var(--text-muted);
  font-size: 11px;
  text-align: right;
}

.priority-assessment {
  margin-top: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-subtle);
}

.priority-assessment__heading,
.priority-result,
.priority-factors dd {
  display: flex;
  align-items: center;
}

.priority-assessment__heading {
  justify-content: space-between;
  gap: var(--space-4);
}

.priority-assessment__heading span {
  font-size: 13px;
  font-weight: 700;
}

.priority-assessment__heading p {
  margin: 2px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.priority-result {
  gap: var(--space-2);
  white-space: nowrap;
}

.priority-result strong {
  font-size: 18px;
}

.priority-factors {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
  margin: var(--space-4) 0 0;
}

.priority-factors > div {
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--surface-raised);
}

.priority-factors dt {
  margin-bottom: var(--space-2);
  color: var(--text-muted);
  font-size: 11px;
}

.priority-factors dd {
  justify-content: space-between;
  gap: var(--space-2);
  margin: 0;
}

.priority-factors dd span {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-factors dd strong {
  color: var(--text-primary);
}

.priority-thresholds {
  margin: var(--space-3) 0 0;
  color: var(--text-muted);
  font-size: 11px;
  text-align: right;
}

.legacy-priority-note {
  margin-top: var(--space-4);
}

.solution-alert {
  margin-bottom: var(--space-4);
}

.solution-diagnosis {
  padding: var(--space-4);
  border-left: 3px solid var(--brand-ai);
  background: var(--surface-subtle);
}

.solution-diagnosis span,
.solution-references > span,
.solution-review > label,
.solution-reject > label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.solution-diagnosis p {
  margin: var(--space-2) 0 0;
  color: var(--text-primary);
  line-height: 1.7;
}

.solution-block {
  margin-top: var(--space-4);
}

.solution-block h3 {
  margin: 0 0 var(--space-2);
  font-size: 14px;
}

.solution-block ul,
.solution-steps {
  margin: 0;
  padding-left: var(--space-6);
  color: var(--text-secondary);
  line-height: 1.8;
}

.solution-empty,
.solution-references p {
  margin: 0;
  color: var(--text-muted);
}

.solution-references {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.solution-references > div {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.solution-references > div span {
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-selected);
  color: var(--brand-hover);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11px;
}

.solution-review-result,
.solution-review {
  margin-top: var(--space-4);
}

.solution-review {
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-default);
}

.solution-review > p {
  margin: var(--space-1) 0 var(--space-3);
  color: var(--text-muted);
  font-size: 12px;
}

.solution-review > .ant-btn {
  margin-top: var(--space-3);
}

.solution-reject {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-default);
}

.solution-reject > div {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) auto;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.similar-list {
  display: grid;
  gap: var(--space-3);
}

.similar-list article {
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}

.similar-item__heading,
.similar-item__title,
.similar-source,
.match-reasons {
  display: flex;
  align-items: center;
}

.similar-item__heading,
.similar-item__title {
  justify-content: space-between;
  gap: var(--space-3);
}

.similar-source {
  gap: var(--space-1);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
}

.similar-score,
.similar-item__title span {
  color: var(--text-muted);
  font-size: 11px;
}

.similar-item__title {
  margin-top: var(--space-2);
}

.similar-list article > p,
.similar-resolution p {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.similar-resolution {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-left: 3px solid var(--border-default);
  background: var(--surface-subtle);
}

.similar-resolution > span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}

.match-reasons {
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.match-reasons span {
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-selected);
  color: var(--brand-hover);
  font-size: 11px;
}

.empty-ai-icon {
  color: var(--brand-ai);
  font-size: 32px;
}

.judgment-timeline {
  margin: var(--space-2) 0 -12px 4px;
}

.judgment-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
}

.judgment-row strong {
  display: block;
  margin-bottom: 2px;
  font-size: 13px;
}

.judgment-row span {
  color: var(--text-secondary);
}

.judgment-row time {
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.handling-panel {
  position: sticky;
  top: calc(var(--header-height) + var(--space-5));
  padding: var(--space-5);
}

.closed-icon {
  color: var(--status-success);
  font-size: 22px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.confirm-button {
  margin: calc(var(--space-2) * -1) 0 var(--space-4);
}

.handling-panel :deep(.ant-divider) {
  margin: var(--space-4) 0;
}

.handling-panel :deep(.ant-radio-group) {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}

.handling-panel :deep(.ant-radio-button-wrapper) {
  padding-inline: 0;
  text-align: center;
}

.closed-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: #dffcf0;
  color: var(--status-success);
  font-weight: 600;
}

.result-hint {
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .workbench-grid {
    grid-template-columns: 1fr;
  }

  .handling-panel {
    position: static;
  }
}

@media (max-width: 640px) {
  .ticket-heading {
    flex-direction: column;
  }

  .analysis-grid,
  .field-grid,
  .priority-factors {
    grid-template-columns: 1fr;
  }

  .priority-assessment__heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .analysis-grid__wide {
    grid-column: auto;
  }

  .judgment-row {
    flex-direction: column;
    gap: var(--space-1);
  }

  .similar-item__heading,
  .similar-item__title {
    align-items: flex-start;
    flex-direction: column;
  }

  .solution-reject > div {
    grid-template-columns: 1fr;
  }
}
</style>
