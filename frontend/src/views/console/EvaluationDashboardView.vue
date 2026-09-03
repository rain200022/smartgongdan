<script setup lang="ts">
import { ReloadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { computed, onMounted, ref } from 'vue'

import { getMVPMetrics, runSearchEvaluation } from '@/api/evaluation'
import type { MVPMetrics, RejectionCategory } from '@/api/types'

const loading = ref(true)
const runningSearch = ref(false)
const errorMessage = ref('')
const metrics = ref<MVPMetrics | null>(null)

const failedSearchCases = computed(
  () => metrics.value?.latest_search_evaluation?.details.filter((item) => item.recall_at_5 < 1) ?? [],
)

onMounted(loadMetrics)

async function loadMetrics(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    metrics.value = await getMVPMetrics()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '评估指标加载失败'
  } finally {
    loading.value = false
  }
}

async function evaluateSearch(): Promise<void> {
  runningSearch.value = true
  try {
    const result = await runSearchEvaluation()
    metrics.value = await getMVPMetrics()
    message.success(`检索评估完成，Recall@5 为 ${formatPercent(result.recall_at_5)}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '检索评估运行失败')
  } finally {
    runningSearch.value = false
  }
}

function formatPercent(value: number | null): string {
  return value === null ? '暂无数据' : `${Math.round(value * 100)}%`
}

function progressPercent(value: number | null): number {
  return Math.round((value ?? 0) * 100)
}

function formatMinutes(value: number | null): string {
  if (value === null) return '暂无数据'
  if (value < 60) return `${Math.round(value)} 分钟`
  return `${(value / 60).toFixed(1)} 小时`
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

function rejectionLabel(category: RejectionCategory): string {
  return {
    EVIDENCE_MISMATCH: '证据不匹配',
    ALREADY_TRIED: '步骤已经尝试',
    RISK_OR_INCOMPLETE: '风险或信息不足',
    OTHER: '其他原因',
  }[category]
}
</script>

<template>
  <section class="evaluation-page">
    <header class="page-heading">
      <div>
        <p class="page-eyebrow">MVP EVALUATION</p>
        <h1>效果评估</h1>
        <p>用固定口径判断 AI 是否真的降低了工单处理成本。</p>
      </div>
      <div class="page-actions">
        <a-button :loading="loading" @click="loadMetrics">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <a-button type="primary" :loading="runningSearch" @click="evaluateSearch">
          运行 Recall@5 评估
        </a-button>
      </div>
    </header>

    <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage" />
    <a-skeleton v-else-if="loading || !metrics" active :paragraph="{ rows: 10 }" />

    <template v-else>
      <div class="metric-grid">
        <article class="metric-card">
          <span>分类完全一致率</span>
          <strong>{{ formatPercent(metrics.classification.exact_agreement_rate) }}</strong>
          <a-progress
            :percent="progressPercent(metrics.classification.exact_agreement_rate)"
            :show-info="false"
            size="small"
          />
          <p>{{ metrics.classification.exact_matches }} / {{ metrics.classification.evaluated_tickets }} 张已评估工单</p>
        </article>

        <article class="metric-card">
          <span>检索 Recall@5</span>
          <strong>{{ formatPercent(metrics.latest_search_evaluation?.recall_at_5 ?? null) }}</strong>
          <a-progress
            :percent="progressPercent(metrics.latest_search_evaluation?.recall_at_5 ?? null)"
            :show-info="false"
            size="small"
          />
          <p>
            {{ metrics.latest_search_evaluation?.query_count ?? 0 }} 条版本化检索用例
          </p>
        </article>

        <article class="metric-card">
          <span>建议采纳率</span>
          <strong>{{ formatPercent(metrics.solutions.adoption_rate) }}</strong>
          <a-progress
            :percent="progressPercent(metrics.solutions.adoption_rate)"
            :show-info="false"
            size="small"
          />
          <p>{{ metrics.solutions.adopted_suggestions }} / {{ metrics.solutions.reviewed_suggestions }} 条已审核建议</p>
        </article>

        <article class="metric-card">
          <span>平均处理时长</span>
          <strong>{{ formatMinutes(metrics.handling_time.average_resolution_minutes) }}</strong>
          <div class="metric-card__divider" />
          <p>{{ metrics.handling_time.resolved_tickets }} 张真实关闭工单</p>
        </article>
      </div>

      <div class="evaluation-grid">
        <section class="content-panel">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">AI 建议</p>
              <h2>审核与采纳</h2>
            </div>
            <span>{{ metrics.solutions.generated_suggestions }} 条已生成</span>
          </div>
          <dl class="count-grid">
            <div><dt>待审核</dt><dd>{{ metrics.solutions.pending_suggestions }}</dd></div>
            <div><dt>已采纳</dt><dd>{{ metrics.solutions.adopted_suggestions }}</dd></div>
            <div><dt>已拒绝</dt><dd>{{ metrics.solutions.rejected_suggestions }}</dd></div>
            <div><dt>平均审核耗时</dt><dd>{{ formatMinutes(metrics.solutions.average_review_minutes) }}</dd></div>
          </dl>
          <div class="reason-list">
            <h3>拒绝原因分布</h3>
            <a-empty
              v-if="!metrics.solutions.rejection_categories.length"
              :image="undefined"
              description="暂无结构化拒绝记录"
            />
            <div
              v-for="item in metrics.solutions.rejection_categories"
              v-else
              :key="item.category"
              class="reason-row"
            >
              <span>{{ rejectionLabel(item.category) }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </section>

        <section class="content-panel">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">处理效率</p>
              <h2>关闭工单耗时</h2>
            </div>
          </div>
          <dl class="duration-summary">
            <div>
              <dt>平均值</dt>
              <dd>{{ formatMinutes(metrics.handling_time.average_resolution_minutes) }}</dd>
            </div>
            <div>
              <dt>中位数</dt>
              <dd>{{ formatMinutes(metrics.handling_time.median_resolution_minutes) }}</dd>
            </div>
          </dl>
          <a-alert
            type="info"
            show-icon
            message="只统计用户实际提交并已关闭的工单；示例历史案例不会进入处理时长。"
          />
        </section>

        <section class="content-panel search-evaluation">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">检索质量</p>
              <h2>Recall@5 基准</h2>
            </div>
          </div>
          <a-empty
            v-if="!metrics.latest_search_evaluation"
            description="尚未运行检索基准评估"
          >
            <a-button type="primary" :loading="runningSearch" @click="evaluateSearch">
              立即运行
            </a-button>
          </a-empty>
          <template v-else>
            <dl class="benchmark-meta">
              <div><dt>数据集</dt><dd>{{ metrics.latest_search_evaluation.dataset_name }}</dd></div>
              <div><dt>版本</dt><dd>{{ metrics.latest_search_evaluation.dataset_version }}</dd></div>
              <div><dt>向量模型</dt><dd>{{ metrics.latest_search_evaluation.embedding_model }}</dd></div>
              <div><dt>运行时间</dt><dd>{{ formatDate(metrics.latest_search_evaluation.created_at) }}</dd></div>
            </dl>
            <div class="failed-cases">
              <h3>未完全召回的用例</h3>
              <a-empty
                v-if="!failedSearchCases.length"
                :image="undefined"
                description="所有用例均完全召回"
              />
              <article v-for="item in failedSearchCases" v-else :key="item.case_id">
                <strong>{{ item.case_id }} · {{ formatPercent(item.recall_at_5) }}</strong>
                <p>期望：{{ item.expected_references.join('、') }}</p>
                <p>召回：{{ item.retrieved_references.join('、') || '无' }}</p>
              </article>
            </div>
          </template>
        </section>

        <section class="content-panel metric-definition">
          <div class="panel-heading">
            <div>
              <p class="panel-eyebrow">统计口径</p>
              <h2>如何理解这些数字</h2>
            </div>
          </div>
          <dl>
            <div>
              <dt>完全一致率</dt>
              <dd>最新一次人工确认与对应 AI 判断的一级、二级分类都相同。</dd>
            </div>
            <div>
              <dt>Recall@5</dt>
              <dd>每条基准查询的期望知识或案例出现在前五名中的比例，再对全部查询取平均。</dd>
            </div>
            <div>
              <dt>建议采纳率</dt>
              <dd>已采纳建议数除以已完成人工审核的建议数，待审核建议不进入分母。</dd>
            </div>
            <div>
              <dt>处理时长</dt>
              <dd>真实工单从创建到关闭的时间；导入的历史案例不进入统计。</dd>
            </div>
          </dl>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.evaluation-page {
  width: min(100%, 1240px);
  margin: 0 auto;
}

.page-heading,
.page-actions,
.panel-heading,
.reason-row {
  display: flex;
  align-items: center;
}

.page-heading {
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.page-heading h1 {
  margin: 0 0 var(--space-1);
  font-size: 28px;
}

.page-heading > div > p:last-child {
  margin: 0;
  color: var(--text-secondary);
}

.page-eyebrow,
.panel-eyebrow {
  margin: 0 0 var(--space-1);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.page-actions {
  gap: var(--space-2);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.metric-card,
.content-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--surface-raised);
}

.metric-card {
  min-width: 0;
  padding: var(--space-4);
}

.metric-card > span {
  color: var(--text-secondary);
  font-size: 13px;
}

.metric-card > strong {
  display: block;
  margin: var(--space-2) 0;
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1.2;
}

.metric-card > p {
  margin: var(--space-2) 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.metric-card__divider {
  height: 4px;
  margin: var(--space-3) 0 var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--surface-subtle);
}

.evaluation-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.content-panel {
  min-width: 0;
  padding: var(--space-5);
}

.panel-heading {
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.panel-heading h2 {
  margin: 0;
  font-size: 17px;
}

.panel-heading > span {
  color: var(--text-muted);
  font-size: 12px;
}

.count-grid,
.duration-summary,
.benchmark-meta {
  display: grid;
  gap: 1px;
  overflow: hidden;
  margin: 0;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--border-default);
}

.count-grid,
.benchmark-meta {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.duration-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: var(--space-4);
}

.count-grid > div,
.duration-summary > div,
.benchmark-meta > div {
  padding: var(--space-3);
  background: var(--surface-raised);
}

.count-grid dt,
.duration-summary dt,
.benchmark-meta dt {
  color: var(--text-muted);
  font-size: 11px;
}

.count-grid dd,
.duration-summary dd,
.benchmark-meta dd {
  margin: var(--space-1) 0 0;
  color: var(--text-primary);
  font-weight: 650;
  overflow-wrap: anywhere;
}

.reason-list,
.failed-cases {
  margin-top: var(--space-4);
}

.reason-list h3,
.failed-cases h3 {
  margin: 0 0 var(--space-3);
  font-size: 13px;
}

.reason-row {
  justify-content: space-between;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-default);
  color: var(--text-secondary);
}

.reason-row:last-child {
  border-bottom: 0;
}

.search-evaluation,
.metric-definition {
  grid-column: 1 / -1;
}

.failed-cases {
  display: grid;
  gap: var(--space-2);
}

.failed-cases article {
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}

.failed-cases article p {
  margin: var(--space-1) 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.metric-definition dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  margin: 0;
}

.metric-definition dt {
  margin-bottom: var(--space-1);
  color: var(--text-primary);
  font-weight: 650;
}

.metric-definition dd {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

@media (max-width: 1000px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .page-heading {
    flex-direction: column;
  }

  .page-actions {
    width: 100%;
  }

  .page-actions .ant-btn {
    flex: 1;
  }

  .metric-grid,
  .evaluation-grid,
  .count-grid,
  .duration-summary,
  .benchmark-meta,
  .metric-definition dl {
    grid-template-columns: 1fr;
  }

  .search-evaluation,
  .metric-definition {
    grid-column: auto;
  }
}
</style>
