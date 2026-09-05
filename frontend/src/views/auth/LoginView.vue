<script setup lang="ts">
import { LockOutlined, UserOutlined } from '@ant-design/icons-vue'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'
import { homeForRole, signIn } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const submitting = ref(false)
const errorMessage = ref('')
const form = reactive({ username: '', password: '' })

function safeRedirect(): string | null {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : null
}

async function submit(): Promise<void> {
  if (submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const user = await signIn(form.username.trim(), form.password)
    await router.replace(safeRedirect() ?? homeForRole(user.role))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="login-title">
      <header class="login-heading">
        <AppLogo />
        <p>统一服务支持入口</p>
        <h1 id="login-title">登录智能工单系统</h1>
        <span>使用管理员为你分配的内部账号</span>
      </header>

      <a-alert
        v-if="route.query.expired === '1'"
        class="login-error"
        type="warning"
        show-icon
        message="登录已过期，请重新登录。同一账号的未提交草稿会在本标签页恢复。"
      />

      <a-alert
        v-if="errorMessage"
        class="login-error"
        type="error"
        show-icon
        :message="errorMessage"
      />

      <a-form :model="form" layout="vertical" @finish="submit">
        <a-form-item
          label="用户名"
          name="username"
          :rules="[{ required: true, message: '请输入用户名' }]"
        >
          <a-input v-model:value="form.username" autocomplete="username" placeholder="请输入用户名">
            <template #prefix><UserOutlined /></template>
          </a-input>
        </a-form-item>
        <a-form-item
          label="密码"
          name="password"
          :rules="[
            { required: true, message: '请输入密码' },
            { min: 8, message: '密码至少 8 个字符' },
          ]"
        >
          <a-input-password
            v-model:value="form.password"
            autocomplete="current-password"
            placeholder="请输入密码"
          >
            <template #prefix><LockOutlined /></template>
          </a-input-password>
        </a-form-item>
        <a-button type="primary" html-type="submit" aria-label="登录" block :loading="submitting">
          登录
        </a-button>
      </a-form>

      <footer class="login-footer">
        没有账号？请联系系统管理员开通，暂不支持公开注册。
      </footer>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: var(--space-6);
  background: var(--surface-canvas);
}

.login-card {
  width: min(100%, 420px);
  padding: var(--space-8);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
  box-shadow: 0 8px 24px rgb(9 30 66 / 8%);
}

.login-heading {
  margin-bottom: var(--space-6);
}

.login-heading > p {
  margin: var(--space-4) 0 var(--space-1);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.login-heading h1 {
  margin: 0 0 var(--space-2);
  font-size: 26px;
  letter-spacing: -0.025em;
}

.login-heading > span,
.login-footer {
  color: var(--text-secondary);
  font-size: 13px;
}

.login-error {
  margin-bottom: var(--space-4);
}

.login-footer {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-default);
  text-align: center;
}

@media (max-width: 480px) {
  .login-page {
    align-items: start;
    padding: var(--space-4);
  }

  .login-card {
    margin-top: var(--space-8);
    padding: var(--space-6) var(--space-5);
  }
}
</style>
