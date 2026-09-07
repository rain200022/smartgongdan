export type TicketStatus = 'open' | 'in_progress' | 'closed'
export type TicketPriority = 'P1' | 'P2' | 'P3' | 'P4'
export type ImpactLevel = '核心业务受影响' | '业务功能受限' | '个人工作受影响' | '轻微影响'
export type UrgencyLevel = '高' | '中' | '低'
export type AffectedScope = '全公司' | '多部门' | '多用户' | '单用户'
export type ClassificationTree = Record<string, string[]>
export type UserRole = 'USER' | 'ENGINEER' | 'ADMIN'

export interface AuthUser {
  id: number
  username: string
  display_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Ticket {
  id: number
  version: number
  requester_id: number | null
  assigned_engineer_id: number | null
  assigned_engineer_name: string | null
  title: string
  description: string
  user_category: string | null
  final_category: string | null
  ai_priority: TicketPriority | null
  final_priority: TicketPriority | null
  resolution: string | null
  status: TicketStatus
  created_at: string
  updated_at: string
  resolved_at: string | null
}

export interface TicketCreate {
  title: string
  description: string
  user_category?: string
}

export interface TicketList {
  items: Ticket[]
  total: number
  limit: number
  offset: number
  status_counts: Record<TicketStatus | 'all', number>
}

export interface APIErrorBody {
  detail?: string | Array<{ loc: Array<string | number>; msg: string }>
}

export interface TicketAIAnalysis {
  id: number
  ticket_id: number
  summary: string
  category: string
  subcategory: string
  device: string | null
  symptom: string | null
  error_message: string | null
  attempted_actions: string[]
  confidence: number
  impact: ImpactLevel | null
  urgency: UrgencyLevel | null
  affected_scope: AffectedScope | null
  impact_score: number | null
  urgency_score: number | null
  scope_score: number | null
  priority_score: number | null
  calculated_priority: TicketPriority | null
  model_name: string
  created_at: string
}

export type SimilarSourceType = 'knowledge' | 'historical_ticket'

export interface SimilarResult {
  source_type: SimilarSourceType
  source_id: number
  reference: string
  title: string
  excerpt: string
  category: string
  subcategory: string
  resolution: string | null
  keyword_score: number | null
  semantic_score: number | null
  combined_score: number
  match_reasons: string[]
  created_at: string
}

export interface SimilarResultList {
  items: SimilarResult[]
  query_model: string
}

export type SolutionReviewDecision = 'ADOPTED' | 'REJECTED'
export type RejectionCategory =
  | 'EVIDENCE_MISMATCH'
  | 'ALREADY_TRIED'
  | 'RISK_OR_INCOMPLETE'
  | 'OTHER'

export interface TicketSolutionReview {
  id: number
  solution_id: number
  ticket_id: number
  reviewer_user_id: number
  decision: SolutionReviewDecision
  engineer_solution: string | null
  rejection_reason: string | null
  rejection_category: RejectionCategory | null
  created_at: string
}

export interface TicketAISolution {
  id: number
  ticket_id: number
  diagnosis: string
  possible_causes: string[]
  steps: string[]
  referenced_cases: string[]
  need_human: boolean
  model_name: string
  created_at: string
  review: TicketSolutionReview | null
}

export interface TicketSolutionReviewCreate {
  decision: SolutionReviewDecision
  engineer_solution?: string
  rejection_reason?: string
  rejection_category?: RejectionCategory
}

export interface ClassificationMetrics {
  confirmed_tickets: number
  evaluated_tickets: number
  category_matches: number
  exact_matches: number
  category_agreement_rate: number | null
  exact_agreement_rate: number | null
}

export interface SearchEvaluationDetail {
  case_id: string
  expected_references: string[]
  retrieved_references: string[]
  matched_references: string[]
  recall_at_5: number
}

export interface SearchEvaluationRun {
  id: number
  dataset_name: string
  dataset_version: string
  query_count: number
  recall_at_5: number
  embedding_model: string
  details: SearchEvaluationDetail[]
  created_at: string
}

export interface SolutionMetrics {
  generated_suggestions: number
  reviewed_suggestions: number
  pending_suggestions: number
  adopted_suggestions: number
  rejected_suggestions: number
  adoption_rate: number | null
  average_review_minutes: number | null
  rejection_categories: Array<{ category: RejectionCategory; count: number }>
}

export interface HandlingTimeMetrics {
  resolved_tickets: number
  average_resolution_minutes: number | null
  median_resolution_minutes: number | null
}

export interface MVPMetrics {
  classification: ClassificationMetrics
  solutions: SolutionMetrics
  handling_time: HandlingTimeMetrics
  latest_search_evaluation: SearchEvaluationRun | null
}

export type JudgeType = 'USER' | 'AI' | 'ENGINEER'

export interface Judgment {
  id: number
  ticket_id: number
  judge_type: JudgeType
  category: string
  subcategory: string
  confidence: number | null
  created_at: string
}

export interface ClassificationEvaluation {
  id: number
  ticket_id: number
  ai_judgment_id: number
  engineer_judgment_id: number
  category_agreement: boolean
  subcategory_agreement: boolean
  agreement: boolean
  created_at: string
}

export interface ClassificationConfirmation {
  ticket_id: number
  final_category: string
  engineer_judgment: Judgment
  compared_ai_judgment: Judgment | null
  evaluation: ClassificationEvaluation | null
}

export interface TicketClose {
  final_category: string
  final_priority: TicketPriority
  resolution: string
}
