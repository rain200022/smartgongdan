<script setup lang="ts">
import { LogoutOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'
import { session, signOut } from '@/stores/session'

const router = useRouter()

async function logout(): Promise<void> {
  await signOut()
  await router.replace('/login')
}
</script>

<template>
  <div class="portal-shell">
    <header class="portal-header">
      <div class="portal-header__inner">
        <router-link to="/portal/tickets/new" class="portal-brand">
          <AppLogo />
        </router-link>
        <nav class="portal-nav" aria-label="用户端主导航">
          <router-link to="/portal/tickets/new" class="portal-nav__link">提交工单</router-link>
          <router-link to="/portal/tickets" class="portal-nav__link">我的工单</router-link>
        </nav>
        <div class="portal-account">
          <span><UserOutlined /> {{ session.state.user?.display_name }}</span>
          <a-button type="text" class="portal-help" aria-label="退出登录" @click="logout">
            <template #icon><LogoutOutlined /></template>
            退出
          </a-button>
        </div>
      </div>
    </header>
    <main class="portal-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.portal-shell {
  min-height: 100vh;
  background: var(--surface-canvas);
}

.portal-header {
  height: var(--header-height);
  border-bottom: 1px solid var(--border-default);
  background: var(--surface-raised);
}

.portal-header__inner {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  width: min(100% - 48px, var(--content-max));
  height: 100%;
  margin: 0 auto;
  align-items: center;
}

.portal-brand {
  width: max-content;
}

.portal-nav {
  display: flex;
  gap: var(--space-6);
  height: 100%;
}

.portal-nav__link {
  display: flex;
  height: 100%;
  align-items: center;
  border-bottom: 2px solid transparent;
  color: var(--text-primary);
  font-weight: 600;
}

.portal-nav__link.router-link-active {
  border-bottom-color: var(--brand-primary);
  color: var(--brand-primary);
}

.portal-help {
  color: var(--text-secondary);
}

.portal-account {
  display: flex;
  align-items: center;
  justify-self: end;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: 13px;
}

.portal-main {
  width: min(100% - 48px, var(--content-max));
  margin: 0 auto;
  padding: var(--space-8) 0 var(--space-12);
}

@media (max-width: 640px) {
  .portal-header__inner,
  .portal-main {
    width: min(100% - 32px, var(--content-max));
  }

  .portal-header__inner {
    grid-template-columns: 1fr auto;
  }

  .portal-nav {
    display: none;
  }

  .portal-account > span {
    display: none;
  }
}
</style>
