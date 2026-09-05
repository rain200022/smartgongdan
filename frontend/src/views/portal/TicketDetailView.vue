<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { APIError } from '@/api/client'
import { getTicket } from '@/api/tickets'
import type { Ticket } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const ticket = ref<Ticket | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const inaccessible = ref(false)
let requestSequence = 0

const backLink = computed(() => {
  const value = route.query.returnTo
  return typeof value === 'string' && (value === '/portal/tickets' || value.startsWith('/portal/tickets?'))
    ? value
    : '/portal/tickets'
})
const statusDescription = computed(() => {
  if (ticket.value?.status === 'closed') return '此工单已关闭，请查看下方最终解决方案。'
  if (ticket.value?.status === 'in_progress') return '工程师正在处理您的问题，可在此刷新查看最新状态。'
  return '工单已提交，等待工程师处理。您可以稍后回到此处查看进度。'
})

async function loadTicket(): Promise<void> {
  const requestId = ++requestSequence
  const ticketId = Number(route.params.ticketId)
  ticket.value = null
  errorMessage.value = ''
  inaccessible.value = false
  if (!Number.isSafeInteger(ticketId) || ticketId <= 0) {
    inaccessible.value = true
    errorMessage.value = '工单不存在或您无权查看。请返回我的工单列表。'
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await getTicket(ticketId)
    if (requestId === requestSequence) ticket.value = result
  } catch (error) {
    if (requestId !== requestSequence) return
    inaccessible.value = error instanceof APIError && (error.status === 403 || error.status === 404)
    errorMessage.value = inaccessible.value
      ? '工单不存在或您无权查看。请返回我的工单列表。'
      : error instanceof Error ? error.message : '工单加载失败，请重试。'
  } finally {
    if (requestId === requestSequence) loading.value = false
  }
}

watch(() => route.params.ticketId, () => { void loadTicket() }, { immediate: true })
onBeforeUnmount(() => { requestSequence += 1 })

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}
</script>

<template>
  <section class="ticket-detail" aria-label="工单详情">
    <div class="detail-toolbar">
      <router-link :to="backLink">返回我的工单</router-link>
      <a-button v-if="!inaccessible" :loading="loading" @click="loadTicket">刷新工单</a-button>
    </div>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage">
      <template v-if="!inaccessible" #action><a-button size="small" @click="loadTicket">重试</a-button></template>
    </a-alert>
    <a-skeleton v-else-if="loading" active :paragraph="{ rows: 8 }" aria-label="正在加载工单详情" />
    <template v-else-if="ticket">
      <header class="detail-heading">
        <div class="ticket-meta">
          <span>INC-{{ String(ticket.id).padStart(4, '0') }}</span>
          <StatusTag :value="ticket.status" />
        </div>
        <h1>{{ ticket.title }}</h1>
        <p>{{ statusDescription }}</p>
      </header>

      <dl class="detail-facts">
        <div><dt>提交时间</dt><dd><time :datetime="ticket.created_at">{{ formatDate(ticket.created_at) }}</time></dd></div>
        <div><dt>最近更新</dt><dd><time :datetime="ticket.updated_at">{{ formatDate(ticket.updated_at) }}</time></dd></div>
        <div v-if="ticket.resolved_at"><dt>关闭时间</dt><dd><time :datetime="ticket.resolved_at">{{ formatDate(ticket.resolved_at) }}</time></dd></div>
        <div><dt>提交分类</dt><dd>{{ ticket.user_category || '未指定' }}</dd></div>
        <div><dt>最终分类</dt><dd>{{ ticket.final_category || '待确认' }}</dd></div>
      </dl>

      <section class="detail-section" aria-labelledby="description-title">
        <h2 id="description-title">问题描述</h2>
        <p class="ticket-content">{{ ticket.description }}</p>
      </section>

      <section v-if="ticket.status === 'closed'" class="detail-section" aria-labelledby="resolution-title">
        <h2 id="resolution-title">最终解决方案</h2>
        <p class="ticket-content">{{ ticket.resolution || '暂无解决方案记录，请联系服务支持。' }}</p>
        <p class="resolution-note">如问题仍然存在，请提交新工单，并注明此工单编号以便工程师跟进。</p>
        <router-link v-slot="{ href, navigate }" to="/portal/tickets/new" custom>
          <a-button :href="href" @click="navigate">提交新工单</a-button>
        </router-link>
      </section>
    </template>
  </section>
</template>

<style scoped>
.ticket-detail {
  width: min(100%, var(--content-max));
  margin: 0 auto;
}

.detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.ticket-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-secondary);
  font-size: 13px;
}

.ticket-meta > span:first-child {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.detail-heading h1 {
  margin: var(--space-3) 0;
  font-size: 28px;
  overflow-wrap: anywhere;
}

.detail-heading p,
.resolution-note {
  color: var(--text-secondary);
}

.detail-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5);
  margin: var(--space-6) 0;
  padding: var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--surface-subtle);
}

.detail-facts dt {
  margin-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: 12px;
}

.detail-facts dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.detail-section {
  margin-top: var(--space-5);
  padding: var(--space-6);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
}

.detail-section h2 {
  margin: 0 0 var(--space-4);
  font-size: 18px;
}

.ticket-content {
  margin: 0;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .detail-facts { grid-template-columns: 1fr; }
  .detail-section { padding: var(--space-4); }
  .detail-heading h1 { font-size: 24px; }
}
</style>
