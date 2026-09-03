<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listTickets } from '@/api/tickets'
import type { Ticket } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const loading = ref(true)
const errorMessage = ref('')
const tickets = ref<Ticket[]>([])

onMounted(async () => {
  try {
    tickets.value = (await listTickets({ limit: 50 })).items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工单加载失败'
  } finally {
    loading.value = false
  }
})

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
      <router-link to="/portal/tickets/new">
        <a-button type="primary">提交新工单</a-button>
      </router-link>
    </header>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage" />
    <a-skeleton v-else-if="loading" active :paragraph="{ rows: 6 }" />
    <a-empty v-else-if="!tickets.length" description="还没有提交过工单">
      <router-link to="/portal/tickets/new"><a-button>提交第一个工单</a-button></router-link>
    </a-empty>
    <div v-else class="ticket-list">
      <article v-for="ticket in tickets" :key="ticket.id" class="ticket-row">
        <div class="ticket-row__main">
          <div class="ticket-row__meta">
            <span>INC-{{ String(ticket.id).padStart(4, '0') }}</span>
            <StatusTag :value="ticket.status" />
          </div>
          <h2>{{ ticket.title }}</h2>
          <p>{{ ticket.description }}</p>
        </div>
        <div class="ticket-row__side">
          <time>{{ formatDate(ticket.created_at) }}</time>
          <span>{{ ticket.final_category || ticket.user_category || '待分类' }}</span>
        </div>
      </article>
    </div>
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
