import type { APIErrorBody } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'
let sessionEpoch = 0
let unauthorizedHandler: (() => void) | undefined

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

export function advanceSessionEpoch(): void {
  sessionEpoch += 1
}

export class APIError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'APIError'
  }
}

function errorMessage(body: APIErrorBody, fallback: string): string {
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg).join('；')
  return fallback
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const requestEpoch = sessionEpoch
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as APIErrorBody
    if (response.status === 401 && path !== '/auth/login' && requestEpoch === sessionEpoch) {
      unauthorizedHandler?.()
    }
    throw new APIError(errorMessage(body, `请求失败（${response.status}）`), response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
