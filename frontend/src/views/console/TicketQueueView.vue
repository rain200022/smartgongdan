<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listTickets } from '@/api/tickets'
import type { Ticket, TicketStatus } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const loading = ref(true)
const errorMessage = ref('')
const tickets = ref<Ticket[]>([])
const statusFilter = ref<TicketStatus | 'all'>('all')

const filteredTickets = computed(() =>
  statusFilter.value === 'all'
    ? tickets.value
    : tickets.value.filter((ticket) => ticket.status === statusFilter.value),
)

const counts = computed(() => ({
  all: tickets.value.length,
  open: tickets.value.filter((ticket) => ticket.status === 'open').length,
  in_progress: tickets.value.filter((ticket) => ticket.status === 'in_progress').length,
  closed: tickets.value.filter((ticket) => ticket.status === 'closed').length,
}))

const columns = [
  { title: '工单', key: 'ticket' },
  { title: '状态', key: 'status', width: 110 },
  { title: '分类', key: 'category', width: 150 },
  { title: '优先级', key: 'priority', width: 110 },
  { title: '创建时间', key: 'created_at', width: 160 },
]

onMounted(async () => {
  try {
    tickets.value = (await listTickets({ limit: 100 })).items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工单队列加载失败'
  } finally {
    loading.value = false
  }
})

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function openTicket(ticket: Ticket): void {
  void router.push(`/console/tickets/${ticket.id}`)
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
    </header>

    <div class="queue-stats" role="group" aria-label="工单状态筛选">
      <button
        v-for="item in [
          { value: 'all', label: '全部' },
          { value: 'open', label: '待处理' },
          { value: 'in_progress', label: '处理中' },
          { value: 'closed', label: '已关闭' },
        ]"
        :key="item.value"
        type="button"
        class="stat-button"
        :class="{ 'stat-button--active': statusFilter === item.value }"
        @click="statusFilter = item.value as TicketStatus | 'all'"
      >
        <strong>{{ counts[item.value as keyof typeof counts] }}</strong>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage" />
    <div v-else class="queue-table">
      <a-table
        :columns="columns"
        :data-source="filteredTickets"
        :loading="loading"
        :pagination="{ pageSize: 20, hideOnSinglePage: true }"
        :row-key="(record: Ticket) => record.id"
        :custom-row="(record: Ticket) => ({ onClick: () => openTicket(record) })"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'ticket'">
            <div class="ticket-cell">
              <span>INC-{{ String(record.id).padStart(4, '0') }}</span>
              <strong>{{ record.title }}</strong>
            </div>
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
        </template>
      </a-table>
    </div>
  </section>
</template>

<style scoped>
.queue-page {
  width: min(100%, 1320px);
  margin: 0 auto;
}

.queue-heading {
  margin-bottom: var(--space-5);
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

.queue-table :deep(.ant-table-tbody > tr) {
  cursor: pointer;
}

.ticket-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
