import { request } from './client'
import type { MVPMetrics, SearchEvaluationRun } from './types'

export function getMVPMetrics(): Promise<MVPMetrics> {
  return request('/metrics/mvp')
}

export function runSearchEvaluation(): Promise<SearchEvaluationRun> {
  return request('/metrics/search/run', { method: 'POST' })
}
