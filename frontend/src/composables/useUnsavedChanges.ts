import { Modal } from 'ant-design-vue'
import { onBeforeUnmount, onMounted, type Ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'

import { session } from '@/stores/session'

export function useUnsavedChanges(dirty: Ref<boolean>, busy?: Ref<boolean>): void {
  async function confirmLeave(): Promise<boolean> {
    if (session.state.expired || !session.state.user) return true
    if (!dirty.value && !busy?.value) return true
    return new Promise((resolve) => {
      Modal.confirm({
        title: busy?.value ? '操作仍在进行，确认离开？' : '有未提交的内容，确认离开？',
        content: '当前草稿会在本标签页中保留；刷新或关闭标签页会丢失草稿。',
        okText: '离开页面',
        cancelText: '继续编辑',
        onOk: () => { resolve(true) },
        onCancel: () => { resolve(false) },
      })
    })
  }

  function beforeUnload(event: BeforeUnloadEvent): void {
    if (dirty.value || busy?.value) {
      event.preventDefault()
      event.returnValue = ''
    }
  }

  onBeforeRouteLeave(confirmLeave)
  onBeforeRouteUpdate((to, from) => to.path === from.path ? true : confirmLeave())
  onMounted(() => window.addEventListener('beforeunload', beforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
}
