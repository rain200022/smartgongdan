<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listTickets } from '@/api/tickets'
import type { Ticket, TicketList, TicketPriority, TicketStatus } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const route = useRoute()
const pageSize = 20
const loading = ref(false)
const errorMessage = ref('')
const tickets = ref<Ticket[]>([])
const total = ref(0)
const searchInput = ref('')
const counts = ref<TicketList['status_counts']>({ all: 0, open: 0, in_progress: 0, closed: 0 })
const statusOptions: Array<{ value: TicketStatus | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' },
  { value: 'closed', label: '已关闭' },
]
const priorityOptions = [
  { value: 'all', label: '全部优先级' },
  { value: 'P1', label: 'P1 紧急' },
  { value: 'P2', label: 'P2 高' },
  { value: 'P3', label: 'P3 普通' },
  { value: 'P4', label: 'P4 低' },
]
const statusFilter = computed<TicketStatus | 'all'>(() => {
  const value = route.query.status
  return value === 'open' || value === 'in_progress' || value === 'closed' ? value : 'all'
})
const priorityFilter = computed<TicketPriority | 'all'>(() => {
  const value = route.query.priority
  return value === 'P1' || value === 'P2' || value === 'P3' || value === 'P4' ? value : 'all'
})
const query = computed(() => typeof route.query.q === 'string' ? route.query.q.trim().slice(0, 200) : '')
const page = computed(() => {
  const value = Number(route.query.page)
  return Number.isSafeInteger(value) && value > 0 && value <= 1000000 ? value : 1
})
const hasFilters = computed(() => statusFilter.value !== 'all' || priorityFilter.value !== 'all' || Boolean(query.value))
let requestSequence = 0

const columns = [
  { title: '工单', key: 'ticket' },
  { title: '状态', key: 'status', width: 110 },
  { title: '分类', key: 'category', width: 150 },
  { title: '优先级', key: 'priority', width: 110 },
  { title: '负责人', key: 'assignee', width: 130 },
  { title: '创建时间', key: 'created_at', width: 160 },
]

async function loadTickets(): Promise<void> {
  const requestId = ++requestSequence
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await listTickets({
      ...(statusFilter.value !== 'all' ? { status: statusFilter.value } : {}),
      ...(priorityFilter.value !== 'all' ? { priority: priorityFilter.value } : {}),
      ...(query.value ? { q: query.value } : {}),
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    })
    if (requestId !== requestSequence) return
    if (page.value > 1 && (page.value - 1) * pageSize >= result.total) {
      await router.replace({ query: { ...route.query, page: String(Math.max(1, Math.ceil(result.total / pageSize))) } })
      return
    }
    tickets.value = result.items
    total.value = result.total
    counts.value = result.status_counts
  } catch (error) {
    if (requestId === requestSequence) errorMessage.value = error instanceof Error ? error.message : '工单队列加载失败'
  } finally {
    if (requestId === requestSequence) loading.value = false
  }
}

watch([statusFilter, priorityFilter, query, page], () => {
  searchInput.value = query.value
  void loadTickets()
}, { immediate: true })

onBeforeUnmount(() => { requestSequence += 1 })

function changeStatus(status: TicketStatus | 'all'): void {
  void router.push({ query: { ...route.query, status: status === 'all' ? undefined : status, page: undefined } })
}

function changePriority(priority: string): void {
  void router.push({ query: { ...route.query, priority: priority === 'all' ? undefined : priority, page: undefined } })
}

function search(): void {
  void router.push({ query: { ...route.query, q: searchInput.value.trim() || undefined, page: undefined } })
}

function changePage(value: number): void {
  void router.push({ query: { ...route.query, page: value === 1 ? undefined : String(value) } })
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

</script>

<template>
  <section class="queue-page" aria-labelledby="queue-title">
    <header class="queue-heading">
      <div>
        <p>工程师工作台</p>
        <h1 id="queue-title">工单队列</h1>
        <span>按状态查看、选择并进入具体工单处理。</span>
      </div>
      <a-button :loading="loading" @click="loadTickets">刷新列表</a-button>
    </header>

    <div class="queue-toolbar">
      <a-input-search
        v-model:value="searchInput"
        aria-label="搜索工单"
        placeholder="搜索标题或工单编号"
        :maxlength="200"
        allow-clear
        enter-button="搜索"
        @search="search"
      />
      <a-select
        aria-label="优先级筛选"
        :value="priorityFilter"
        :options="priorityOptions"
        @change="(value) => changePriority(String(value))"
      />
      <a-button v-if="hasFilters" @click="router.push({ path: '/console/tickets' })">清除筛选</a-button>
    </div>
    <p class="counts-note">状态数量按当前搜索和优先级统计。</p>
    <div class="queue-stats" role="group" aria-label="工单状态筛选">
      <button
        v-for="item in statusOptions"
        :key="item.value"
        type="button"
        class="stat-button"
        :class="{ 'stat-button--active': statusFilter === item.value }"
        :aria-pressed="statusFilter === item.value"
        @click="changeStatus(item.value)"
      >
        <strong>{{ loading || errorMessage ? '—' : counts[item.value] }}</strong>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage">
      <template #action><a-button size="small" @click="loadTickets">重试</a-button></template>
    </a-alert>
    <div v-else class="queue-table">
      <a-table
        :columns="columns"
        :data-source="loading ? [] : tickets"
        :loading="loading"
        :pagination="false"
        :row-key="(record: Ticket) => record.id"
        :scroll="{ x: 800 }"
      >
        <template #emptyText>
          <a-empty v-if="!loading" :description="hasFilters ? '没有符合条件的工单' : '暂无工单'" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'ticket'">
            <router-link
              class="ticket-cell"
              :to="{ path: `/console/tickets/${record.id}`, query: { returnTo: route.fullPath } }"
            >
              <span>INC-{{ String(record.id).padStart(4, '0') }}</span>
              <strong>{{ record.title }}</strong>
            </router-link>
          </template>
          <template v-else-if="column.key === 'status'">
            <StatusTag :value="record.status" />
          </template>
          <template v-else-if="column.key === 'category'">
            {{ record.final_category || record.user_category || '待分类' }}
          </template>
          <template v-else-if="column.key === 'priority'">
            <StatusTag v-if="record.final_priority ?? record.ai_priority" :value="record.final_priority ?? record.ai_priority" />
            <span v-else>—</span>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'assignee'">
            {{ record.assigned_engineer_name || '未认领' }}
          </template>
        </template>
      </a-table>
    </div>
    <a-pagination
      v-if="!errorMessage && total > 0"
      class="queue-pagination"
      :current="page"
      :page-size="pageSize"
      :total="total"
      :show-size-changer="false"
      :disabled="loading"
      :show-total="(count: number) => `共 ${count} 条工单`"
      @change="changePage"
    />
  </section>
</template>

<style scoped>
.queue-page {
  width: min(100%, 1320px);
  margin: 0 auto;
}

.queue-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.queue-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.queue-toolbar :deep(.ant-input-search) {
  width: min(100%, 480px);
}

.queue-toolbar :deep(.ant-select) {
  min-width: 150px;
}

.counts-note {
  margin: 0 0 var(--space-3);
  color: var(--text-secondary);
  font-size: 12px;
}

.queue-pagination {
  margin-top: var(--space-5);
}

.queue-heading p {
  margin: 0 0 var(--space-1);
  color: var(--brand-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.queue-heading h1 {
  margin: 0 0 var(--space-1);
  font-size: 28px;
}

.queue-heading span {
  color: var(--text-secondary);
}

.queue-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.stat-button {
  display: flex;
  min-height: 72px;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  background: var(--surface-raised);
  cursor: pointer;
}

.stat-button strong {
  color: var(--text-primary);
  font-size: 24px;
}

.stat-button--active {
  border-color: var(--brand-primary);
  background: var(--surface-selected);
}

.stat-button--active strong,
.stat-button--active span {
  color: var(--brand-primary);
}

.queue-table {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
}

.ticket-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--brand-primary);
  overflow-wrap: anywhere;
}

.ticket-cell span {
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11px;
}

@media (max-width: 720px) {
  .queue-stats {
    grid-template-columns: 1fr 1fr;
  }

  .queue-table {
    overflow-x: auto;
  }
}
</style>
