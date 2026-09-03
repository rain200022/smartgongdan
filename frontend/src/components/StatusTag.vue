<script setup lang="ts">
import { computed } from 'vue'

import type { TicketPriority, TicketStatus } from '@/api/types'

const props = defineProps<{
  value: TicketStatus | TicketPriority
}>()

const config = computed(() => {
  const map: Record<TicketStatus | TicketPriority, { label: string; tone: string }> = {
    open: { label: '待处理', tone: 'neutral' },
    in_progress: { label: '处理中', tone: 'info' },
    closed: { label: '已关闭', tone: 'success' },
    P1: { label: 'P1 紧急', tone: 'danger' },
    P2: { label: 'P2 高', tone: 'warning' },
    P3: { label: 'P3 普通', tone: 'info' },
    P4: { label: 'P4 低', tone: 'neutral' },
  }
  return map[props.value]
})
</script>

<template>
  <span class="status-tag" :class="`status-tag--${config.tone}`">{{ config.label }}</span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
  white-space: nowrap;
}

.status-tag--neutral {
  background: #f1f2f4;
  color: #44546f;
}

.status-tag--info {
  background: #e9f2ff;
  color: #0055cc;
}

.status-tag--success {
  background: #dffcf0;
  color: #216e4e;
}

.status-tag--warning {
  background: #fff7d6;
  color: #7f5f01;
}

.status-tag--danger {
  background: #ffeceb;
  color: #ae2e24;
}
</style>
