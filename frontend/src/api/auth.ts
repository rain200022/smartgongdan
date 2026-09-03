import { request } from './client'
import type { AuthUser, UserRole } from './types'

export interface LoginPayload {
  username: string
  password: string
}

export interface UserCreatePayload {
  username: string
  display_name: string
  password: string
  role: UserRole
}

export function login(payload: LoginPayload): Promise<AuthUser> {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function logout(): Promise<void> {
  return request('/auth/logout', { method: 'POST' })
}

export function getCurrentUser(): Promise<AuthUser> {
  return request('/auth/me')
}

export function listUsers(): Promise<AuthUser[]> {
  return request('/users')
}

export function createUser(payload: UserCreatePayload): Promise<AuthUser> {
  return request('/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateUserStatus(userId: number, isActive: boolean): Promise<AuthUser> {
  return request(`/users/${userId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: isActive }),
  })
}

export function resetUserPassword(userId: number, newPassword: string): Promise<AuthUser> {
  return request(`/users/${userId}/password/reset`, {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  })
}
