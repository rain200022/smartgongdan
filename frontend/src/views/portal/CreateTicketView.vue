<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { createTicket, getClassificationTree } from '@/api/tickets'
import type { ClassificationTree, Ticket } from '@/api/types'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { readDraft, removeDraft, saveDraft } from '@/stores/drafts'
import { session } from '@/stores/session'

interface TicketForm {
  title: string
  description: string
  category?: string
  subcategory?: string
  device: string
  errorMessage: string
  attemptedActions: string
}

const formRef = ref()
const submitting = ref(false)
const loadError = ref('')
const submitError = ref('')
const createdTicket = ref<Ticket | null>(null)
const classificationTree = ref<ClassificationTree>({})
const form = reactive<TicketForm>({
  title: '',
  description: '',
  category: undefined,
  subcategory: undefined,
  device: '',
  errorMessage: '',
  attemptedActions: '',
})
const draftOwner = session.state.user!.id
const draftKey = 'create-ticket'
const savedDraft = readDraft<TicketForm>(draftOwner, draftKey)
if (savedDraft) Object.assign(form, savedDraft)
const dirty = computed(() => !createdTicket.value && Object.values(form).some(Boolean))
useUnsavedChanges(dirty, submitting)
watch(form, () => {
  if (session.state.user?.id !== draftOwner && !session.state.expired) return
  if (dirty.value) saveDraft(draftOwner, draftKey, form)
  else removeDraft(draftOwner, draftKey)
}, { deep: true, flush: 'sync' })

const categories = computed(() => Object.keys(classificationTree.value))
const subcategories = computed(() =>
  form.category ? (classificationTree.value[form.category] ?? []) : [],
)

onMounted(async () => {
  try {
    classificationTree.value = await getClassificationTree()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '分类加载失败'
  }
})

function resetSubcategory(): void {
  form.subcategory = undefined
}

function buildDescription(): string {
  const details = [form.description.trim()]
  if (form.device.trim()) details.push(`设备或环境：${form.device.trim()}`)
  if (form.errorMessage.trim()) details.push(`错误提示：${form.errorMessage.trim()}`)
  if (form.attemptedActions.trim()) details.push(`已尝试操作：${form.attemptedActions.trim()}`)
  return details.join('\n\n')
}

async function submit(): Promise<void> {
  if (submitting.value) return
  submitError.value = ''
  if (!form.title.trim() || !form.description.trim()) {
    submitError.value = '请输入有效的问题标题和详情'
    return
  }
  if (buildDescription().length > 10000) {
    submitError.value = '问题详情与补充上下文合计不能超过 10000 个字符，请精简后提交'
    return
  }
  submitting.value = true
  try {
    const userCategory =
      form.category && form.subcategory ? `${form.category}/${form.subcategory}` : undefined
    createdTicket.value = await createTicket({
      title: form.title.trim(),
      description: buildDescription(),
      ...(userCategory ? { user_category: userCategory } : {}),
    })
    removeDraft(draftOwner, draftKey)
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '工单提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function createAnother(): void {
  createdTicket.value = null
  Object.assign(form, {
    title: '',
    description: '',
    category: undefined,
    subcategory: undefined,
    device: '',
    errorMessage: '',
    attemptedActions: '',
  })
  formRef.value?.clearValidate()
}
</script>

<template>
  <section class="create-ticket" aria-labelledby="page-title">
    <template v-if="createdTicket">
      <a-result status="success" title="工单已提交" sub-title="我们已经记录你的问题，工程师会尽快处理。">
        <template #extra>
          <div class="success-ticket">工单编号：INC-{{ String(createdTicket.id).padStart(4, '0') }}</div>
          <router-link v-slot="{ href, navigate }" :to="`/portal/tickets/${createdTicket.id}`" custom>
            <a-button type="primary" :href="href" @click="navigate">查看工单详情</a-button>
          </router-link>
          <router-link v-slot="{ href, navigate }" to="/portal/tickets" custom>
            <a-button :href="href" @click="navigate">查看我的工单</a-button>
          </router-link>
          <a-button @click="createAnother">继续提交工单</a-button>
        </template>
      </a-result>
    </template>

    <template v-else>
      <header class="page-heading">
        <p class="page-eyebrow">服务支持</p>
        <h1 id="page-title">提交一个新工单</h1>
        <p>清楚描述问题和你已经尝试过的操作，有助于工程师更快定位。</p>
      </header>

      <a-alert
        v-if="loadError"
        class="form-alert"
        type="warning"
        show-icon
        message="分类暂时不可用，你仍然可以正常提交工单。"
      />
      <a-alert
        v-if="submitError"
        class="form-alert"
        type="error"
        show-icon
        :message="submitError"
      />

      <div class="form-panel">
        <a-form ref="formRef" :model="form" :disabled="submitting" layout="vertical" @finish="submit">
          <section class="form-section" aria-labelledby="problem-section-title">
            <div class="section-heading">
              <span class="section-number">1</span>
              <div>
                <h2 id="problem-section-title">描述遇到的问题</h2>
                <p>请避免填写密码、验证码或其他敏感信息。</p>
              </div>
            </div>

            <a-form-item
              label="问题标题"
              name="title"
              :rules="[
                { required: true, message: '请输入问题标题' },
                { max: 200, message: '标题不能超过 200 个字符' },
              ]"
            >
              <a-input v-model:value="form.title" :maxlength="200" placeholder="例如：VPN 提示认证服务器不可用" />
            </a-form-item>

            <a-form-item
              label="问题详情"
              name="description"
              :rules="[
                { required: true, message: '请描述遇到的问题' },
                { max: 9000, message: '问题详情过长，请精简后重试' },
              ]"
            >
              <a-textarea
                v-model:value="form.description"
                :rows="6"
                show-count
                :maxlength="9000"
                placeholder="什么时候开始出现？对工作有什么影响？可以稳定复现吗？"
              />
            </a-form-item>
          </section>

          <a-divider />

          <section class="form-section" aria-labelledby="context-section-title">
            <div class="section-heading">
              <span class="section-number section-number--optional">2</span>
              <div>
                <h2 id="context-section-title">补充上下文 <span>选填</span></h2>
                <p>这些信息会一并交给工程师和 AI 分析模块。</p>
              </div>
            </div>

            <div class="field-grid">
              <a-form-item label="问题类别" name="category">
                <a-select
                  v-model:value="form.category"
                  allow-clear
                  placeholder="选择一级分类"
                  :options="categories.map((value) => ({ value, label: value }))"
                  @change="resetSubcategory"
                />
              </a-form-item>
              <a-form-item label="具体类型" name="subcategory">
                <a-select
                  v-model:value="form.subcategory"
                  allow-clear
                  :disabled="!form.category"
                  placeholder="选择二级分类"
                  :options="subcategories.map((value) => ({ value, label: value }))"
                />
              </a-form-item>
            </div>

            <a-form-item label="设备或环境" name="device">
              <a-input v-model:value="form.device" placeholder="例如：Windows 11 笔记本、公司网络" />
            </a-form-item>
            <a-form-item label="错误提示" name="errorMessage">
              <a-input v-model:value="form.errorMessage" placeholder="请原样填写关键错误信息" />
            </a-form-item>
            <a-form-item label="已经尝试过的操作" name="attemptedActions">
              <a-textarea
                v-model:value="form.attemptedActions"
                :rows="3"
                placeholder="例如：重启 VPN 客户端、切换网络，问题仍然存在"
              />
            </a-form-item>
          </section>

          <footer class="form-actions">
            <span>提交后会生成可追踪的工单编号</span>
            <a-button type="primary" html-type="submit" :loading="submitting">提交工单</a-button>
          </footer>
        </a-form>
      </div>
    </template>
  </section>
</template>

<style scoped>
.create-ticket {
  width: min(100%, var(--form-max));
  margin: 0 auto;
}

.page-heading {
  margin-bottom: var(--space-6);
}

.page-eyebrow {
  margin-bottom: var(--space-2) !important;
  color: var(--brand-primary) !important;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0 0 var(--space-2);
  font-size: clamp(26px, 4vw, 32px);
  line-height: 1.25;
  letter-spacing: -0.03em;
}

.page-heading p,
.section-heading p {
  margin: 0;
  color: var(--text-secondary);
}

.form-alert {
  margin-bottom: var(--space-4);
}

.form-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
  box-shadow: var(--shadow-subtle);
}

.form-section {
  padding: var(--space-6);
}

.section-heading {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.section-heading h2 {
  margin: 0 0 var(--space-1);
  font-size: 18px;
  line-height: 1.4;
}

.section-heading h2 span {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 400;
}

.section-heading p {
  font-size: 13px;
}

.section-number {
  display: grid;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-primary);
  color: white;
  font-size: 13px;
  font-weight: 700;
}

.section-number--optional {
  background: var(--surface-selected);
  color: var(--brand-primary);
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-default);
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  background: var(--surface-subtle);
}

.form-actions span {
  color: var(--text-secondary);
  font-size: 13px;
}

.success-ticket {
  margin-bottom: var(--space-4);
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

@media (max-width: 640px) {
  .form-section {
    padding: var(--space-5) var(--space-4);
  }

  .field-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .form-actions {
    align-items: stretch;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
  }
}
</style>
