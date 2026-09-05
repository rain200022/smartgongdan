import { computed, reactive, readonly } from 'vue'

import { advanceSessionEpoch, setUnauthorizedHandler } from '@/api/client'
import * as authApi from '@/api/auth'
import type { AuthUser, UserRole } from '@/api/types'
import { clearDrafts } from '@/stores/drafts'

const state = reactive({
  user: null as AuthUser | null,
  initialized: false,
  expired: false,
})
let draftOwnerId: number | null = null
let initialization: Promise<AuthUser | null> | null = null

setUnauthorizedHandler(() => {
  if (!state.user) return
  state.user = null
  state.expired = true
  advanceSessionEpoch()
})

const isStaff = computed(
  () => state.user?.role === 'ENGINEER' || state.user?.role === 'ADMIN',
)

export async function ensureSession(): Promise<AuthUser | null> {
  if (state.initialized) return state.user
  if (initialization) return initialization
  initialization = (async () => {
    try {
      state.user = await authApi.getCurrentUser()
      draftOwnerId = state.user.id
    } catch {
      state.user = null
    } finally {
      state.initialized = true
      initialization = null
    }
    return state.user
  })()
  return initialization
}

export async function signIn(username: string, password: string): Promise<AuthUser> {
  const user = await authApi.login({ username, password })
  if (draftOwnerId !== null && draftOwnerId !== user.id) clearDrafts()
  draftOwnerId = user.id
  advanceSessionEpoch()
  state.user = user
  state.initialized = true
  state.expired = false
  return user
}

export async function signOut(): Promise<void> {
  try {
    await authApi.logout()
  } finally {
    state.user = null
    state.initialized = true
    state.expired = false
    draftOwnerId = null
    advanceSessionEpoch()
    clearDrafts()
  }
}

export function homeForRole(role: UserRole): string {
  return role === 'USER' ? '/portal/tickets/new' : '/console/tickets'
}

export const session = {
  state: readonly(state),
  isStaff,
}
