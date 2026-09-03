<script setup lang="ts">
import { KeyOutlined, PlusOutlined, UserOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createUser,
  listUsers,
  resetUserPassword,
  updateUserStatus,
} from '@/api/auth'
import type { AuthUser, UserRole } from '@/api/types'
import { session } from '@/stores/session'

const loading = ref(true)
const actionUserId = ref<number | null>(null)
const errorMessage = ref('')
const users = ref<AuthUser[]>([])
const createOpen = ref(false)
const resetTarget = ref<AuthUser | null>(null)
const createSubmitting = ref(false)
const resetSubmitting = ref(false)
const createError = ref('')
const resetError = ref('')
const createForm = reactive({
  username: '',
  display_name: '',
  password: '',
  role: 'USER' as UserRole,
})
const resetForm = reactive({ new_password: '', confirm_password: '' })

const columns = [
  { title: '账号', key: 'account' },
  { title: '角色', key: 'role', width: 130 },
  { title: '状态', key: 'status', width: 110 },
  { title: '创建时间', key: 'created_at', width: 170 },
  { title: '操作', key: 'actions', width: 240 },
]

const activeCount = computed(() => users.value.filter((user) => user.is_active).length)

onMounted(loadUsers)

async function loadUsers(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    users.value = await listUsers()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '账号列表加载失败'
  } finally {
    loading.value = false
  }
}

function roleLabel(role: UserRole): string {
  return { USER: '普通用户', ENGINEER: '工程师', ADMIN: '管理员' }[role]
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

function openCreate(): void {
  Object.assign(createForm, {
    username: '',
    display_name: '',
    password: '',
    role: 'USER' as UserRole,
  })
  createError.value = ''
  createOpen.value = true
}

async function submitCreate(): Promise<void> {
  createError.value = ''
  if (!/^[a-zA-Z0-9_.-]{3,64}$/.test(createForm.username.trim())) {
    createError.value = '用户名需为 3–64 位字母、数字、点、下划线或连字符'
    return
  }
  if (!createForm.display_name.trim()) {
    createError.value = '请输入显示名称'
    return
  }
  if (createForm.password.length < 10) {
    createError.value = '初始密码至少需要 10 个字符'
    return
  }
  createSubmitting.value = true
  try {
    const user = await createUser({
      username: createForm.username.trim().toLowerCase(),
      display_name: createForm.display_name.trim(),
      password: createForm.password,
      role: createForm.role,
    })
    users.value.push(user)
    createOpen.value = false
    message.success(`账号 ${user.username} 已创建`)
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '账号创建失败'
  } finally {
    createSubmitting.value = false
  }
}

async function toggleStatus(userRecord: Partial<AuthUser>): Promise<void> {
  const user = users.value.find((item) => item.id === userRecord.id)
  if (!user) return
  actionUserId.value = user.id
  try {
    const updated = await updateUserStatus(user.id, !user.is_active)
    const index = users.value.findIndex((item) => item.id === user.id)
    if (index >= 0) users.value[index] = updated
    message.success(updated.is_active ? '账号已启用' : '账号已停用，会话已撤销')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '状态更新失败')
  } finally {
    actionUserId.value = null
  }
}

function openReset(userRecord: Partial<AuthUser>): void {
  const user = users.value.find((item) => item.id === userRecord.id)
  if (!user) return
  resetTarget.value = user
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetError.value = ''
}

async function submitReset(): Promise<void> {
  if (!resetTarget.value) return
  resetError.value = ''
  if (resetForm.new_password.length < 10) {
    resetError.value = '新密码至少需要 10 个字符'
    return
  }
  if (resetForm.new_password !== resetForm.confirm_password) {
    resetError.value = '两次输入的密码不一致'
    return
  }
  resetSubmitting.value = true
  try {
    await resetUserPassword(resetTarget.value.id, resetForm.new_password)
    message.success(`已重置 ${resetTarget.value.username} 的密码并撤销其会话`)
    resetTarget.value = null
  } catch (error) {
    resetError.value = error instanceof Error ? error.message : '密码重置失败'
  } finally {
    resetSubmitting.value = false
  }
}
</script>

<template>
  <section class="users-page" aria-labelledby="users-title">
    <header class="users-heading">
      <div>
        <p>系统管理</p>
        <h1 id="users-title">账号管理</h1>
        <span>创建内部账号并管理其访问状态，公开注册保持关闭。</span>
      </div>
      <a-button type="primary" @click="openCreate">
        <template #icon><PlusOutlined /></template>
        创建账号
      </a-button>
    </header>

    <div class="summary-row" aria-label="账号概况">
      <div>
        <strong>{{ users.length }}</strong>
        <span>全部账号</span>
      </div>
      <div>
        <strong>{{ activeCount }}</strong>
        <span>已启用</span>
      </div>
      <div>
        <strong>{{ users.length - activeCount }}</strong>
        <span>已停用</span>
      </div>
    </div>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage" />
    <div v-else class="users-table">
      <a-table
        :columns="columns"
        :data-source="users"
        :loading="loading"
        :pagination="{ pageSize: 20, hideOnSinglePage: true }"
        :row-key="(record: AuthUser) => record.id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'account'">
            <div class="account-cell">
              <span class="account-avatar"><UserOutlined /></span>
              <div>
                <strong>
                  {{ record.display_name }}
                  <small v-if="record.id === session.state.user?.id">当前</small>
                </strong>
                <span>@{{ record.username }}</span>
              </div>
            </div>
          </template>
          <template v-else-if="column.key === 'role'">
            <span class="role-badge">{{ roleLabel(record.role) }}</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <span class="state-badge" :class="{ 'state-badge--inactive': !record.is_active }">
              {{ record.is_active ? '已启用' : '已停用' }}
            </span>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <div class="action-group">
              <a-button
                type="link"
                size="small"
                :disabled="record.id === session.state.user?.id"
                @click="openReset(record)"
              >
                <template #icon><KeyOutlined /></template>
                重置密码
              </a-button>
              <a-popconfirm
                :title="record.is_active ? '确认停用该账号？' : '确认重新启用该账号？'"
                :description="record.is_active ? '停用后该账号的所有登录会话会立即失效。' : '启用后该账号可以重新登录。'"
                ok-text="确认"
                cancel-text="取消"
                :disabled="record.id === session.state.user?.id"
                @confirm="toggleStatus(record)"
              >
                <a-button
                  type="link"
                  size="small"
                  :danger="record.is_active"
                  :disabled="record.id === session.state.user?.id"
                  :loading="actionUserId === record.id"
                >
                  {{ record.is_active ? '停用' : '启用' }}
                </a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal v-model:open="createOpen" title="创建内部账号" :footer="null" :width="520">
      <a-alert
        v-if="createError"
        class="modal-alert"
        type="error"
        show-icon
        :message="createError"
      />
      <a-form layout="vertical" @finish="submitCreate">
        <div class="form-grid">
          <a-form-item label="用户名" required>
            <a-input v-model:value="createForm.username" placeholder="例如：zhangsan" />
          </a-form-item>
          <a-form-item label="显示名称" required>
            <a-input v-model:value="createForm.display_name" placeholder="例如：张三" />
          </a-form-item>
        </div>
        <a-form-item label="角色" required>
          <a-select
            v-model:value="createForm.role"
            :options="[
              { value: 'USER', label: '普通用户 · 提交和查看自己的工单' },
              { value: 'ENGINEER', label: '工程师 · 查看并处理全部工单' },
              { value: 'ADMIN', label: '管理员 · 工程师权限与账号管理' },
            ]"
          />
        </a-form-item>
        <a-form-item label="初始密码" required extra="至少 10 个字符，请通过安全渠道交给用户。">
          <a-input-password
            v-model:value="createForm.password"
            autocomplete="new-password"
            placeholder="输入初始密码"
          />
        </a-form-item>
        <div class="modal-actions">
          <a-button @click="createOpen = false">取消</a-button>
          <a-button type="primary" html-type="submit" :loading="createSubmitting">创建账号</a-button>
        </div>
      </a-form>
    </a-modal>

    <a-modal
      :open="Boolean(resetTarget)"
      title="重置账号密码"
      :footer="null"
      :width="480"
      @cancel="resetTarget = null"
    >
      <p class="reset-context">
        正在重置 <strong>{{ resetTarget?.display_name }}</strong>（@{{ resetTarget?.username }}）的密码。完成后该账号的现有会话会失效。
      </p>
      <a-alert
        v-if="resetError"
        class="modal-alert"
        type="error"
        show-icon
        :message="resetError"
      />
      <a-form layout="vertical" @finish="submitReset">
        <a-form-item label="新密码" required>
          <a-input-password
            v-model:value="resetForm.new_password"
            autocomplete="new-password"
            placeholder="至少 10 个字符"
          />
        </a-form-item>
        <a-form-item label="确认新密码" required>
          <a-input-password
            v-model:value="resetForm.confirm_password"
            autocomplete="new-password"
            placeholder="再次输入新密码"
          />
        </a-form-item>
        <div class="modal-actions">
          <a-button @click="resetTarget = null">取消</a-button>
          <a-button type="primary" html-type="submit" :loading="resetSubmitting">确认重置</a-button>
        </div>
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.users-page {
  width: min(100%, 1320px);
  margin: 0 auto;
}

.users-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
}

.users-heading p {
  margin: 0 0 var(--space-1);
  color: var(--brand-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.users-heading h1 {
  margin: 0 0 var(--space-1);
  font-size: 28px;
}

.users-heading span {
  color: var(--text-secondary);
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 220px));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.summary-row > div {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--surface-raised);
}

.summary-row strong {
  font-size: 22px;
}

.summary-row span {
  color: var(--text-secondary);
  font-size: 13px;
}

.users-table {
  overflow: hidden;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
}

.account-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.account-avatar {
  display: grid;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 50%;
  color: var(--brand-primary);
  background: var(--surface-selected);
}

.account-cell strong,
.account-cell > div > span {
  display: block;
}

.account-cell strong small {
  margin-left: var(--space-1);
  color: var(--brand-primary);
  font-size: 11px;
}

.account-cell > div > span {
  color: var(--text-muted);
  font-size: 12px;
}

.role-badge,
.state-badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.role-badge {
  color: var(--brand-primary);
  background: var(--surface-selected);
}

.state-badge {
  color: var(--status-success);
  background: var(--surface-subtle);
}

.state-badge--inactive {
  color: var(--text-muted);
}

.action-group {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.modal-alert {
  margin-bottom: var(--space-4);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}

.reset-context {
  margin: 0 0 var(--space-4);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  background: var(--surface-subtle);
}

@media (max-width: 720px) {
  .users-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .summary-row {
    grid-template-columns: 1fr;
  }

  .users-table {
    overflow-x: auto;
  }

  .form-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
