import { computed, reactive, readonly } from 'vue'

import { APIError } from '@/api/client'
import * as authApi from '@/api/auth'
import type { AuthUser, UserRole } from '@/api/types'

const state = reactive({
  user: null as AuthUser | null,
  initialized: false,
})

const isStaff = computed(
  () => state.user?.role === 'ENGINEER' || state.user?.role === 'ADMIN',
)

export async function ensureSession(): Promise<AuthUser | null> {
  if (state.initialized) return state.user
  try {
    state.user = await authApi.getCurrentUser()
  } catch (error) {
    if (error instanceof APIError && error.status !== 401) {
      // Keep the sign-in surface available while the API is temporarily unavailable.
    }
    state.user = null
  } finally {
    state.initialized = true
  }
  return state.user
}

export async function signIn(username: string, password: string): Promise<AuthUser> {
  const user = await authApi.login({ username, password })
  state.user = user
  state.initialized = true
  return user
}

export async function signOut(): Promise<void> {
  try {
    await authApi.logout()
  } finally {
    state.user = null
    state.initialized = true
  }
}

export function homeForRole(role: UserRole): string {
  return role === 'USER' ? '/portal/tickets/new' : '/console/tickets'
}

export const session = {
  state: readonly(state),
  isStaff,
}
