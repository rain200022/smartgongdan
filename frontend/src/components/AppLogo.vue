<script setup lang="ts">
defineProps<{
  compact?: boolean
}>()
</script>

<template>
  <div class="app-logo" aria-label="智单智能工单系统">
    <span class="app-logo__mark" aria-hidden="true">智</span>
    <span v-if="!compact" class="app-logo__name">智单</span>
  </div>
</template>

<style scoped>
.app-logo {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.app-logo__mark {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-primary);
  color: white;
  font-size: 16px;
}

.app-logo__name {
  font-size: 18px;
}
</style>
