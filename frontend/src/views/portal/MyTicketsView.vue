<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listTickets } from '@/api/tickets'
import type { Ticket, TicketStatus } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const pageSize = 20
const loading = ref(false)
const errorMessage = ref('')
const tickets = ref<Ticket[]>([])
const total = ref(0)
const searchInput = ref('')
const statusOptions: Array<{ value: TicketStatus | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' },
  { value: 'closed', label: '已关闭' },
]
const statusFilter = computed<TicketStatus | 'all'>(() => {
  const value = route.query.status
  return value === 'open' || value === 'in_progress' || value === 'closed' ? value : 'all'
})
const query = computed(() => typeof route.query.q === 'string' ? route.query.q.trim().slice(0, 200) : '')
const page = computed(() => {
  const value = Number(route.query.page)
  return Number.isSafeInteger(value) && value > 0 && value <= 1000000 ? value : 1
})
const hasFilters = computed(() => statusFilter.value !== 'all' || Boolean(query.value))
let requestSequence = 0

async function loadTickets(): Promise<void> {
  const requestId = ++requestSequence
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await listTickets({
      ...(statusFilter.value !== 'all' ? { status: statusFilter.value } : {}),
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
  } catch (error) {
    if (requestId === requestSequence) errorMessage.value = error instanceof Error ? error.message : '工单加载失败'
  } finally {
    if (requestId === requestSequence) loading.value = false
  }
}

watch([statusFilter, query, page], () => {
  searchInput.value = query.value
  void loadTickets()
}, { immediate: true })

onBeforeUnmount(() => { requestSequence += 1 })

function changeStatus(status: TicketStatus | 'all'): void {
  void router.push({ query: { ...route.query, status: status === 'all' ? undefined : status, page: undefined } })
}

function search(): void {
  void router.push({ query: { ...route.query, q: searchInput.value.trim() || undefined, page: undefined } })
}

function changePage(value: number): void {
  void router.push({ query: { ...route.query, page: value === 1 ? undefined : String(value) } })
}

function clearFilters(): void {
  void router.push({ path: '/portal/tickets' })
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}
</script>

<template>
  <section class="my-tickets" aria-labelledby="my-tickets-title">
    <header class="page-heading">
      <div>
        <p>服务支持</p>
        <h1 id="my-tickets-title">我的工单</h1>
        <span>这里只展示由当前账号提交的工单。</span>
      </div>
      <router-link v-slot="{ href, navigate }" to="/portal/tickets/new" custom>
        <a-button type="primary" :href="href" @click="navigate">提交新工单</a-button>
      </router-link>
    </header>

    <div class="list-toolbar">
      <a-input-search
        v-model:value="searchInput"
        aria-label="搜索我的工单"
        placeholder="搜索标题或工单编号"
        :maxlength="200"
        allow-clear
        enter-button="搜索"
        @search="search"
      />
      <a-button :loading="loading" @click="loadTickets">刷新列表</a-button>
    </div>
    <div class="status-filters" role="group" aria-label="我的工单状态筛选">
      <a-button
        v-for="item in statusOptions"
        :key="item.value"
        :type="statusFilter === item.value ? 'primary' : 'default'"
        :aria-pressed="statusFilter === item.value"
        @click="changeStatus(item.value)"
      >{{ item.label }}</a-button>
    </div>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage">
      <template #action><a-button size="small" @click="loadTickets">重试</a-button></template>
    </a-alert>
    <a-skeleton v-else-if="loading" active :paragraph="{ rows: 6 }" aria-label="正在加载工单" />
    <a-empty v-else-if="!tickets.length" :description="hasFilters ? '没有符合条件的工单' : '还没有提交过工单'">
      <a-button v-if="hasFilters" @click="clearFilters">清除筛选</a-button>
      <router-link v-else v-slot="{ href, navigate }" to="/portal/tickets/new" custom>
        <a-button :href="href" @click="navigate">提交第一个工单</a-button>
      </router-link>
    </a-empty>
    <div v-else class="ticket-list">
      <article v-for="ticket in tickets" :key="ticket.id" class="ticket-row">
        <div class="ticket-row__main">
          <div class="ticket-row__meta">
            <span>INC-{{ String(ticket.id).padStart(4, '0') }}</span>
            <StatusTag :value="ticket.status" />
          </div>
          <h2>
            <router-link :to="{ path: `/portal/tickets/${ticket.id}`, query: { returnTo: route.fullPath } }">
              {{ ticket.title }}
            </router-link>
          </h2>
          <p>{{ ticket.description }}</p>
        </div>
        <div class="ticket-row__side">
          <time :datetime="ticket.created_at">{{ formatDate(ticket.created_at) }}</time>
          <span>{{ ticket.final_category || ticket.user_category || '待分类' }}</span>
        </div>
      </article>
    </div>
    <a-pagination
      v-if="!errorMessage && total > 0"
      class="list-pagination"
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
.my-tickets {
  width: min(100%, var(--content-max));
  margin: 0 auto;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-5);
  margin-bottom: var(--space-6);
}

.page-heading p {
  margin: 0 0 var(--space-1);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0 0 var(--space-1);
  font-size: 28px;
}

.page-heading span {
  color: var(--text-secondary);
}

.list-toolbar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.list-toolbar :deep(.ant-input-search) {
  max-width: 520px;
}

.status-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.list-pagination {
  margin-top: var(--space-5);
}

.ticket-list {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
}

.ticket-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-6);
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-default);
}

.ticket-row:last-child {
  border-bottom: 0;
}

.ticket-row__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}

.ticket-row h2 {
  margin: 0 0 var(--space-1);
  font-size: 16px;
}

.ticket-row h2 a {
  color: var(--brand-primary);
  overflow-wrap: anywhere;
}

.ticket-row p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--text-secondary);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.ticket-row__side {
  display: flex;
  min-width: 136px;
  align-items: flex-end;
  flex-direction: column;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 640px) {
  .page-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .ticket-row {
    grid-template-columns: 1fr;
  }

  .ticket-row__side {
    align-items: flex-start;
  }
}
</style>
