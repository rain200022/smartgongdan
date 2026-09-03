<script setup lang="ts">
import {
  BarChartOutlined,
  FileTextOutlined,
  LogoutOutlined,
  SearchOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'
import { session, signOut } from '@/stores/session'

const router = useRouter()
const route = useRoute()
const ticketSearch = ref('')
const currentTicketPath = computed(() =>
  route.name === 'console-ticket-workbench' ? route.fullPath : '/console/tickets',
)

async function logout(): Promise<void> {
  await signOut()
  await router.replace('/login')
}

function openTicket(): void {
  const normalized = ticketSearch.value.trim().replace(/^INC-/i, '')
  const ticketId = Number(normalized)
  if (Number.isInteger(ticketId) && ticketId > 0) {
    void router.push(`/console/tickets/${ticketId}`)
    ticketSearch.value = ''
  }
}
</script>

<template>
  <div class="console-shell">
    <header class="console-header">
      <router-link to="/console/tickets" class="console-brand">
        <AppLogo />
        <span class="console-product">服务管理</span>
      </router-link>
      <a-input-search
        v-model:value="ticketSearch"
        class="console-search"
        placeholder="输入工单编号，如 1001"
        aria-label="按工单编号搜索"
        @search="openTicket"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input-search>
      <div class="console-account">
        <span class="console-account__avatar"><UserOutlined /></span>
        <span>{{ session.state.user?.display_name }}</span>
        <a-button type="text" size="small" aria-label="退出登录" @click="logout">
          <template #icon><LogoutOutlined /></template>
        </a-button>
      </div>
    </header>

    <aside class="console-sidebar" aria-label="管理员端主导航">
      <p class="nav-label">工作台</p>
      <router-link
        to="/console/tickets"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'console-ticket-queue' }"
      >
        <FileTextOutlined />
        工单队列
      </router-link>
      <router-link
        v-if="session.state.user?.role === 'ADMIN'"
        to="/console/users"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'console-user-management' }"
      >
        <TeamOutlined />
        账号管理
      </router-link>
      <router-link
        v-if="route.name === 'console-ticket-workbench'"
        :to="currentTicketPath"
        class="nav-item nav-item--active nav-item--child"
      >
        当前工单
      </router-link>
      <router-link
        to="/console/evaluation"
        class="nav-item"
        :class="{ 'nav-item--active': route.name === 'console-evaluation' }"
      >
        <BarChartOutlined />
        效果评估
      </router-link>
      <div class="nav-item nav-item--disabled" title="将在知识库阶段开放">
        <SettingOutlined />
        系统设置
        <span>稍后</span>
      </div>
      <div class="sidebar-note">
        <strong>M5</strong>
        <p>可复现的 AI 效果评估</p>
      </div>
    </aside>

    <main class="console-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.console-shell {
  min-height: 100vh;
  background: var(--surface-canvas);
}

.console-header {
  position: fixed;
  z-index: 20;
  top: 0;
  right: 0;
  left: 0;
  display: grid;
  height: var(--header-height);
  grid-template-columns: var(--sidebar-width) minmax(240px, 480px) 1fr;
  align-items: center;
  border-bottom: 1px solid var(--border-default);
  background: var(--surface-raised);
}

.console-brand {
  display: flex;
  height: 100%;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-5);
  border-right: 1px solid var(--border-default);
}

.console-product {
  padding-left: var(--space-3);
  border-left: 1px solid var(--border-default);
  color: var(--text-secondary);
  font-size: 13px;
}

.console-search {
  width: min(100%, 400px);
  margin-left: var(--space-6);
}

.console-account {
  display: flex;
  align-items: center;
  justify-self: end;
  gap: var(--space-2);
  margin-right: var(--space-6);
  color: var(--text-secondary);
  font-size: 13px;
}

.console-account__avatar {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-subtle);
}

.console-sidebar {
  position: fixed;
  z-index: 10;
  top: var(--header-height);
  bottom: 0;
  left: 0;
  width: var(--sidebar-width);
  padding: var(--space-5) var(--space-3);
  border-right: 1px solid var(--border-default);
  background: var(--surface-raised);
}

.nav-label {
  margin: 0 var(--space-2) var(--space-2);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
  padding: 0 var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
}

.nav-item--active {
  background: var(--surface-selected);
  color: var(--brand-primary);
  font-weight: 650;
}

.nav-item--disabled {
  cursor: not-allowed;
  opacity: 0.64;
}

.nav-item--child {
  padding-left: 44px;
  font-size: 13px;
}

.nav-item--disabled span:last-child {
  margin-left: auto;
  font-size: 11px;
}

.sidebar-note {
  position: absolute;
  right: var(--space-4);
  bottom: var(--space-4);
  left: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-subtle);
}

.sidebar-note strong {
  color: var(--brand-primary);
  font-size: 12px;
}

.sidebar-note p {
  margin: var(--space-1) 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.console-main {
  min-height: 100vh;
  margin-left: var(--sidebar-width);
  padding: calc(var(--header-height) + var(--space-6)) var(--space-6) var(--space-8);
}

@media (max-width: 900px) {
  .console-header {
    grid-template-columns: auto 1fr auto;
  }

  .console-brand {
    border-right: 0;
  }

  .console-product,
  .console-account span:last-child {
    display: none;
  }

  .console-search {
    margin: 0 var(--space-4);
  }

  .console-sidebar {
    display: none;
  }

  .console-main {
    margin-left: 0;
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }
}
</style>
