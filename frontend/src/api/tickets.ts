import { request } from './client'
import type {
  ClassificationConfirmation,
  ClassificationTree,
  Judgment,
  SimilarResultList,
  Ticket,
  TicketAIAnalysis,
  TicketAISolution,
  TicketClose,
  TicketCreate,
  TicketList,
  TicketPriority,
  TicketStatus,
  TicketSolutionReviewCreate,
} from './types'

export interface TicketEvent {
  id: number
  ticket_id: number
  version: number
  actor_id: number
  actor_name: string
  action: string
  created_at: string
}

function versionHeaders(version: number): Record<string, string> {
  return { 'X-Ticket-Version': String(version) }
}

export function getTicketEvents(ticketId: number, offset = 0): Promise<TicketEvent[]> {
  return request(`/tickets/${ticketId}/events?limit=100&offset=${offset}`)
}

export function claimTicket(ticketId: number, version: number): Promise<Ticket> {
  return request(`/tickets/${ticketId}/claim`, { method: 'POST', headers: versionHeaders(version) })
}

export function releaseTicket(ticketId: number, version: number): Promise<Ticket> {
  return request(`/tickets/${ticketId}/release`, { method: 'POST', headers: versionHeaders(version) })
}

export function getClassificationTree(): Promise<ClassificationTree> {
  return request('/classification-tree')
}

export function createTicket(payload: TicketCreate): Promise<Ticket> {
  return request('/tickets', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listTickets(params: {
  status?: TicketStatus
  q?: string
  priority?: TicketPriority
  limit?: number
  offset?: number
} = {}): Promise<TicketList> {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  if (params.q) search.set('q', params.q)
  if (params.priority) search.set('priority', params.priority)
  search.set('limit', String(params.limit ?? 20))
  search.set('offset', String(params.offset ?? 0))
  return request(`/tickets?${search.toString()}`)
}

export function getTicket(ticketId: number): Promise<Ticket> {
  return request(`/tickets/${ticketId}`)
}

export function updateTicketStatus(ticketId: number, status: TicketStatus, version: number): Promise<Ticket> {
  return request(`/tickets/${ticketId}`, {
    method: 'PATCH',
    headers: versionHeaders(version),
    body: JSON.stringify({ status }),
  })
}

export function analyzeTicket(ticketId: number, version: number): Promise<TicketAIAnalysis> {
  return request(`/tickets/${ticketId}/analyze`, { method: 'POST', headers: versionHeaders(version) })
}

export function getLatestAnalysis(ticketId: number): Promise<TicketAIAnalysis> {
  return request(`/tickets/${ticketId}/analysis/latest`)
}

export function getSimilarResults(ticketId: number, limit = 5): Promise<SimilarResultList> {
  return request(`/tickets/${ticketId}/similar?limit=${limit}`)
}

export function generateSolution(ticketId: number, version: number): Promise<TicketAISolution> {
  return request(`/tickets/${ticketId}/solutions/generate`, { method: 'POST', headers: versionHeaders(version) })
}

export function getLatestSolution(ticketId: number): Promise<TicketAISolution> {
  return request(`/tickets/${ticketId}/solutions/latest`)
}

export function reviewSolution(
  ticketId: number,
  solutionId: number,
  payload: TicketSolutionReviewCreate,
  version: number,
): Promise<TicketAISolution> {
  return request(`/tickets/${ticketId}/solutions/${solutionId}/review`, {
    method: 'POST',
    headers: versionHeaders(version),
    body: JSON.stringify(payload),
  })
}

export function getJudgments(ticketId: number): Promise<Judgment[]> {
  return request(`/tickets/${ticketId}/judgments`)
}

export function confirmClassification(
  ticketId: number,
  category: string,
  subcategory: string,
  version: number,
): Promise<ClassificationConfirmation> {
  return request(`/tickets/${ticketId}/classification/confirm`, {
    method: 'POST',
    headers: versionHeaders(version),
    body: JSON.stringify({ category, subcategory }),
  })
}

export function closeTicket(ticketId: number, payload: TicketClose, version: number): Promise<Ticket> {
  return request(`/tickets/${ticketId}/close`, {
    method: 'POST',
    headers: versionHeaders(version),
    body: JSON.stringify(payload),
  })
}
