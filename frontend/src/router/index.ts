import { createRouter, createWebHistory } from 'vue-router'
import { watch } from 'vue'

import { ensureSession, homeForRole, session } from '@/stores/session'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/portal/tickets/new',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/portal',
      component: () => import('@/layouts/PortalLayout.vue'),
      children: [
        {
          path: 'tickets/new',
          name: 'portal-create-ticket',
          component: () => import('@/views/portal/CreateTicketView.vue'),
          meta: { title: '提交工单', roles: ['USER'] },
        },
        {
          path: 'tickets',
          name: 'portal-my-tickets',
          component: () => import('@/views/portal/MyTicketsView.vue'),
          meta: { title: '我的工单', roles: ['USER'] },
        },
        {
          path: 'tickets/:ticketId',
          name: 'portal-ticket-detail',
          component: () => import('@/views/portal/TicketDetailView.vue'),
          meta: { title: '工单详情', roles: ['USER'] },
        },
      ],
    },
    {
      path: '/console',
      component: () => import('@/layouts/ConsoleLayout.vue'),
      children: [
        {
          path: '',
          redirect: '/console/tickets',
        },
        {
          path: 'tickets',
          name: 'console-ticket-queue',
          component: () => import('@/views/console/TicketQueueView.vue'),
          meta: { title: '工单队列', roles: ['ENGINEER', 'ADMIN'] },
        },
        {
          path: 'tickets/:ticketId',
          name: 'console-ticket-workbench',
          component: () => import('@/views/console/TicketWorkbenchView.vue'),
          meta: { title: '工单处理', roles: ['ENGINEER', 'ADMIN'] },
        },
        {
          path: 'evaluation',
          name: 'console-evaluation',
          component: () => import('@/views/console/EvaluationDashboardView.vue'),
          meta: { title: '效果评估', roles: ['ENGINEER', 'ADMIN'] },
        },
        {
          path: 'users',
          name: 'console-user-management',
          component: () => import('@/views/console/UserManagementView.vue'),
          meta: { title: '账号管理', roles: ['ADMIN'] },
        },
      ],
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const user = await ensureSession()
  if (to.meta.public) {
    return user ? homeForRole(user.role) : true
  }
  if (!user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(user.role)) return homeForRole(user.role)
  return true
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '智能工单')} · 智单`
})

watch(() => session.state.expired, (expired) => {
  const current = router.currentRoute.value
  if (expired && !current.meta.public) {
    void router.replace({ name: 'login', query: { expired: '1', redirect: current.fullPath } })
  }
})

export default router
