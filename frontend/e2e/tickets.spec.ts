import { expect, test, type Page } from '@playwright/test'

const password = 'E2E-Only-Password-2026!'
const oldestTitle = '跨百条分页回归：VPN认证失败'

async function submitLogin(page: Page, username: string): Promise<void> {
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

async function login(page: Page, username: string): Promise<void> {
  await page.goto('/login')
  await submitLogin(page, username)
}

test('用户提交 → 工程师处理并关闭 → 用户查看最终方案', async ({ page, browser }) => {
  await login(page, 'e2e-user')
  const title = `浏览器闭环 VPN 无法连接 ${test.info().retry}`
  await page.getByLabel('问题标题', { exact: true }).fill(title)
  await page.getByLabel('问题详情', { exact: true }).fill('VPN认证服务器不可用，已经重启客户端仍然失败。')
  const created = page.waitForResponse((response) =>
    response.url().endsWith('/api/tickets') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  const response = await created
  expect(response.status()).toBe(201)
  const ticket = await response.json() as { id: number }
  await expect(page.getByText('工单已提交', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: '查看工单详情' }).click()
  await expect(page).toHaveURL(new RegExp(`/portal/tickets/${ticket.id}$`))
  await expect(page.getByRole('heading', { name: title })).toBeVisible()

  const engineerContext = await browser.newContext({ baseURL: test.info().project.use.baseURL })
  const engineer = await engineerContext.newPage()
  await login(engineer, 'e2e-engineer')
  await engineer.goto(`/console/tickets/${ticket.id}`)
  await engineer.getByRole('button', { name: '开始处理', exact: true }).click()
  await expect(engineer.getByRole('button', { name: '开始处理', exact: true })).toHaveCount(0)
  await engineer.getByRole('button', { name: '开始分析', exact: true }).click()
  await expect(engineer.getByRole('button', { name: '重新分析', exact: true })).toBeVisible()
  const resolution = '根因：设备证书过期。重新签发证书后连接 VPN，已验证恢复。'
  await engineer.getByLabel('最终解决方案', { exact: true }).fill(resolution)
  await engineer.getByRole('button', { name: '关闭工单', exact: true }).click()
  await engineer.getByRole('button', { name: '确认关闭', exact: true }).click()
  await expect(engineer.getByText('此工单已经关闭，处理记录保持只读。')).toBeVisible()
  await expect(engineer.getByLabel('最终解决方案', { exact: true })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('heading', { name: '最终解决方案', exact: true })).toBeVisible()
  await expect(page.getByText(resolution, { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: '最终解决方案', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: test.info().outputPath('portal-detail-mobile.png'), fullPage: true })
  await engineerContext.close()
})

test('本人列表和详情隔离其他账号的工单', async ({ page }) => {
  await login(page, 'e2e-user')
  await page.goto('/portal/tickets')
  await page.getByLabel('搜索我的工单').fill('其他用户的私人工单')
  await page.getByLabel('搜索我的工单').press('Enter')
  await expect(page.getByText('没有符合条件的工单')).toBeVisible()
  const response = await page.request.get('/api/tickets/106')
  expect(response.status()).toBe(403)
  await page.goto('/portal/tickets/106')
  await expect(page.getByText('其他用户的私人工单', { exact: true })).toHaveCount(0)
  await expect(page.getByText('工单不存在或您无权查看。请返回我的工单列表。')).toBeVisible()
})

test('用户和工程师都能翻到第 100 条之后并搜索旧工单', async ({ page, browser }) => {
  await login(page, 'e2e-user')
  await page.goto('/portal/tickets')
  await page.getByTitle('6', { exact: true }).click()
  await expect(page).toHaveURL(/page=6/)
  await expect(page.getByRole('link', { name: oldestTitle })).toBeVisible()
  await page.getByRole('link', { name: oldestTitle }).click()
  await expect(page.getByRole('heading', { name: oldestTitle })).toBeVisible()
  await page.getByRole('link', { name: '返回我的工单' }).click()
  await expect(page).toHaveURL(/page=6/)

  const engineerContext = await browser.newContext({ baseURL: test.info().project.use.baseURL })
  const engineer = await engineerContext.newPage()
  await login(engineer, 'e2e-engineer')
  await engineer.getByTitle('6', { exact: true }).click()
  await expect(engineer.getByRole('link', { name: oldestTitle })).toBeVisible()
  await engineer.getByLabel('搜索工单', { exact: true }).fill(oldestTitle)
  await engineer.getByLabel('搜索工单', { exact: true }).press('Enter')
  await expect(engineer.getByRole('link', { name: oldestTitle })).toBeVisible()
  await expect(engineer.getByText('历史工单 002', { exact: true })).toHaveCount(0)
  await expect(engineer).not.toHaveURL(/page=6/)
  await engineerContext.close()
})

test('重新分析保留人工方案和优先级，登录过期后可恢复继续提交', async ({ page }) => {
  await login(page, 'e2e-engineer')
  await page.goto('/console/tickets/1')
  await page.getByRole('button', { name: /^(开始分析|重新分析)$/ }).click()
  await expect(page.getByRole('button', { name: '重新分析', exact: true })).toBeVisible()
  const draft = '尚未提交的现场结论：需要检查设备证书，保留此人工记录。'
  await page.getByLabel('最终解决方案', { exact: true }).fill(draft)
  // Ant Design's native radio input is visually hidden; click its visible label.
  await page.getByText('P1', { exact: true }).click()
  await expect(page.getByRole('radio', { name: 'P1', exact: true })).toBeChecked()
  const analyzed = page.waitForResponse((response) => response.url().endsWith('/tickets/1/analyze'))
  await page.getByRole('button', { name: '重新分析', exact: true }).click()
  await analyzed
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue(draft)
  await expect(page.getByRole('radio', { name: 'P1', exact: true })).toBeChecked()
  await expect(page.getByRole('button', { name: '关闭工单', exact: true })).toBeEnabled()

  await page.context().clearCookies()
  await page.getByRole('button', { name: '关闭工单', exact: true }).click()
  await page.getByRole('button', { name: '确认关闭', exact: true }).click()
  await expect(page).toHaveURL(/\/login\?.*expired=1/)
  await submitLogin(page, 'e2e-engineer')
  await expect(page).toHaveURL(/\/console\/tickets\/1$/)
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue(draft)
  await expect(page.getByRole('radio', { name: 'P1', exact: true })).toBeChecked()
  // The expired submission must not close the ticket or be retried automatically.
  await expect(page.getByRole('button', { name: '关闭工单', exact: true })).toBeVisible()
})

test('用户填写中的工单在登录过期后恢复且只提交一次', async ({ page }) => {
  await login(page, 'e2e-user')
  const title = `登录过期草稿 ${test.info().retry}`
  const description = '已经填写完整的问题内容，重新登录后应仍然存在。'
  await page.getByLabel('问题标题', { exact: true }).fill(title)
  await page.getByLabel('问题详情', { exact: true }).fill(description)
  await page.context().clearCookies()
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  await expect(page).toHaveURL(/\/login\?.*expired=1/)
  await submitLogin(page, 'e2e-user')
  await expect(page.getByLabel('问题标题', { exact: true })).toHaveValue(title)
  await expect(page.getByLabel('问题详情', { exact: true })).toHaveValue(description)
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  await expect(page.getByText('工单已提交', { exact: true })).toBeVisible()
  const response = await page.request.get(`/api/tickets?q=${encodeURIComponent(title)}`)
  const result = await response.json() as { total: number }
  expect(result.total).toBe(1)
})

test('离开前提示未提交内容，并能在本标签页恢复草稿', async ({ page }) => {
  await login(page, 'e2e-user')
  const title = '离开页面仍保留的草稿'
  await page.getByLabel('问题标题', { exact: true }).fill(title)
  await page.getByRole('link', { name: '我的工单', exact: true }).click()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.getByLabel('问题标题', { exact: true })).toHaveValue(title)
  await page.getByRole('link', { name: '我的工单', exact: true }).click()
  await page.getByRole('button', { name: '离开页面', exact: true }).click()
  await expect(page).toHaveURL(/\/portal\/tickets$/)
  await page.getByRole('link', { name: '提交工单', exact: true }).click()
  await expect(page.getByLabel('问题标题', { exact: true })).toHaveValue(title)
})

test('过期后切换账号不显示前一账号的草稿', async ({ page }) => {
  await login(page, 'e2e-user')
  await page.getByLabel('问题标题', { exact: true }).fill('前一账号私有草稿')
  await page.getByLabel('问题详情', { exact: true }).fill('这些内容不能交给另一个登录账号。')
  await page.context().clearCookies()
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  await expect(page).toHaveURL(/\/login\?.*expired=1/)
  await submitLogin(page, 'e2e-other')
  await expect(page.getByLabel('问题标题', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('问题详情', { exact: true })).toHaveValue('')
})

test('切换工单后迟到的请求不会覆盖当前工作台', async ({ page }) => {
  await login(page, 'e2e-engineer')
  let release = (): void => {}
  const pending = new Promise<void>((resolve) => { release = resolve })
  let requested = (): void => {}
  const requestStarted = new Promise<void>((resolve) => { requested = resolve })
  await page.route('**/api/tickets/1', async (route) => {
    const response = await route.fetch()
    requested()
    await pending
    await route.fulfill({ response })
  })
  try {
    await page.getByLabel('按工单编号搜索').fill('1')
    await page.getByLabel('按工单编号搜索').press('Enter')
    await requestStarted
    await page.getByLabel('按工单编号搜索').fill('2')
    await page.getByLabel('按工单编号搜索').press('Enter')
    await expect(page.getByRole('heading', { name: '历史工单 002' })).toBeVisible()
    const oldResponse = page.waitForResponse((response) => response.url().endsWith('/api/tickets/1'))
    release()
    await oldResponse
    await expect(page.getByRole('heading', { name: '历史工单 002' })).toBeVisible()
    await expect(page.getByRole('heading', { name: oldestTitle })).toHaveCount(0)
  } finally {
    release()
  }
})

test('认领隔离其他工程师，释放后可接手，旧版本提交保留草稿', async ({ page, browser }) => {
  await login(page, 'e2e-engineer')
  await page.goto('/console/tickets/3')
  await page.getByRole('button', { name: '认领工单', exact: true }).click()
  await expect(page.getByText('负责人：e2e-engineer · 版本 2', { exact: true })).toBeVisible()
  const secondContext = await browser.newContext({ baseURL: test.info().project.use.baseURL })
  const second = await secondContext.newPage()
  await login(second, 'e2e-engineer-other')
  await second.goto('/console/tickets/3')
  await expect(second.getByText('该工单已由其他工程师认领，当前为只读视图。')).toBeVisible()
  await expect(second.getByLabel('最终解决方案', { exact: true })).toBeDisabled()
  const denied = await second.request.post('/api/tickets/3/claim')
  expect(denied.status()).toBe(403)
  await page.getByRole('button', { name: '释放工单', exact: true }).click()
  await page.getByRole('button', { name: '确认释放', exact: true }).click()
  await expect(page.getByRole('button', { name: '认领工单', exact: true })).toBeEnabled()
  await second.getByRole('button', { name: '加载最新记录', exact: true }).click()
  await second.getByRole('button', { name: '认领工单', exact: true }).click()
  await expect(second.getByText('负责人：e2e-engineer-other · 版本 4', { exact: true })).toBeVisible()
  const draft = '我的现场草稿，不应被冲突或刷新清除。'
  await page.getByLabel('最终解决方案', { exact: true }).fill(draft)
  await page.getByRole('button', { name: '关闭工单', exact: true }).click()
  await page.getByRole('button', { name: '确认关闭', exact: true }).click()
  await expect(page.getByText('未提交草稿仍保留；加载后请核对最新处理记录，再决定是否提交。')).toBeVisible()
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue(draft)
  await page.getByRole('button', { name: '加载最新记录', exact: true }).last().click()
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue(draft)
  await expect(page.getByLabel('最终解决方案', { exact: true })).toBeDisabled()
  await expect(page.getByRole('heading', { name: '操作记录', exact: true })).toBeVisible()
  await secondContext.close()
})

test('同一工程师另一标签页更新后，旧版本关闭返回冲突且不自动重试', async ({ page }) => {
  await login(page, 'e2e-engineer')
  await page.goto('/console/tickets/4')
  await page.getByLabel('最终解决方案', { exact: true }).fill('保留版本冲突现场结论')
  const updated = await page.request.patch('/api/tickets/4', {
    headers: { 'X-Ticket-Version': '1' }, data: { final_priority: 'P1' },
  })
  expect(updated.status()).toBe(200)
  const conflict = page.waitForResponse((response) => response.url().endsWith('/tickets/4/close'))
  await page.getByRole('button', { name: '关闭工单', exact: true }).click()
  await page.getByRole('button', { name: '确认关闭', exact: true }).click()
  expect((await conflict).status()).toBe(409)
  await page.getByRole('button', { name: '加载最新记录', exact: true }).last().click()
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue('保留版本冲突现场结论')
  await expect(page.getByRole('radio', { name: 'P1', exact: true })).toBeChecked()
  const current = await page.request.get('/api/tickets/4')
  expect((await current.json() as { status: string }).status).toBe('open')
})

test('工单已被另一标签页关闭时保留未提交的原方案供复制', async ({ page }) => {
  await login(page, 'e2e-engineer')
  await page.goto('/console/tickets/5')
  await page.getByLabel('最终解决方案', { exact: true }).fill('尚未提交的独立现场记录')
  const response = await page.request.post('/api/tickets/5/close', {
    data: { final_category: '网络/VPN', final_priority: 'P3', resolution: '另一标签页确认已修复' },
  })
  expect(response.status()).toBe(200)
  await page.getByRole('button', { name: '加载最新记录', exact: true }).click()
  await expect(page.getByText('尚未提交的独立现场记录', { exact: true })).toBeVisible()
  await expect(page.getByLabel('最终解决方案', { exact: true })).toHaveValue('另一标签页确认已修复')
  await expect(page.getByLabel('最终解决方案', { exact: true })).toBeDisabled()
})
