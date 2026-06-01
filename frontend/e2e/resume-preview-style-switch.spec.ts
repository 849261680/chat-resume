// 用于验证简历预览在切换模板时尺寸保持稳定。
import { expect, test, type Page } from '@playwright/test'

const authUser = {
  id: 1,
  email: 'style-switch@test.example',
  is_active: true,
  created_at: new Date().toISOString(),
}
const SMART_FIT_TARGET_BOTTOM_GAP = 48
const SMART_FIT_GAP_TOLERANCE = 12

// 构造足够长的简历内容，让预览面板在编辑页中以缩放状态显示。
function buildResumeResponse() {
  const longText = '负责 Agent 简历优化链路，覆盖结构化解析、差距诊断、建议生成和人工确认，确保输出可追踪、可回滚、可解释。'
  return {
    id: 123,
    title: '样式切换测试简历',
    owner_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    content: {
      parsing_quality: 1,
      parsing_method: 'manual',
      job_application: { target_company: '测试公司', target_title: 'Agent 工程师', jd_text: '负责 Agent 开发' },
      personal_info: { name: '样式切换', email: 'style-switch@test.example', phone: '13800000000' },
      education: [{ school: '测试大学', degree: '本科', major: '计算机', duration: '2019-2023' }],
      skills: [{ category: '技术栈', items: ['TypeScript', 'Next.js', 'FastAPI', 'LangChain'] }],
      work_experience: [{ company: '测试科技', position: '核心开发者', duration: '2025.01-2025.12', highlights: [{ text: longText }, { text: longText }] }],
      projects: Array.from({ length: 3 }, (_, index) => ({
        name: `项目 ${index + 1}`,
        role: '核心开发者',
        duration: `2025.0${index + 1}-2025.0${index + 2}`,
        overview: longText,
        highlights: [{ text: longText }, { text: longText }, { text: longText }],
      })),
    },
  }
}

// 安装编辑页依赖的最小 API mock。
async function mockEditorApis(page: Page, resume = buildResumeResponse()) {
  await page.addInitScript((storedUser) => {
    window.localStorage.setItem('auth_user', JSON.stringify(storedUser))
  }, authUser)
  await page.context().addCookies([
    { name: 'refresh_token', value: 'test-refresh-token', domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' },
    { name: 'NEXT_LOCALE', value: 'zh', domain: 'localhost', path: '/', sameSite: 'Lax' },
  ])
  await page.route('**/api/auth/me', async route => route.fulfill({ json: authUser }))
  await page.route('**/api/auth/refresh', async route => route.fulfill({ json: { token_type: 'bearer', user: authUser } }))
  await page.route('**/api/resumes/123/chat-messages', async route => route.fulfill({ json: [] }))
  await page.route('**/api/resumes/123/layout', async route => route.fulfill({ json: { ok: true } }))
  await page.route('**/api/resumes/123', async route => route.fulfill({ json: resume }))
}

// 构造不足一页但包含全部模块的简历，用于验证智能一页的底部对齐。
function buildSmartFitResumeResponse() {
  const resume = buildResumeResponse()
  return {
    ...resume,
    content: {
      ...resume.content,
      summary: { text: '具备前端工程化与 AI 产品经验，关注性能、可用性和端到端交付。' },
      work_experience: [{
        company: '测试公司',
        position: '前端工程师',
        duration: '2022-至今',
        highlights: [
          { text: '负责简历编辑器、实时预览和导出链路，提升用户编辑效率。' },
          { text: '建设组件化设计系统和端到端测试，降低回归风险。' },
          { text: '优化首屏加载和交互性能，改善低端设备体验。' },
        ],
      }],
      projects: [{
        name: 'Chat Resume',
        role: '全栈工程师',
        duration: '2025',
        overview: 'AI 驱动的求职辅导平台，提供简历诊断、模拟面试和岗位匹配能力。',
        highlights: [
          { text: '实现流式对话、差异审阅和一键采纳，形成闭环编辑体验。' },
          { text: '接入简历解析、岗位摘要和智能布局，减少用户手工排版。' },
        ],
      }],
    },
  }
}

// 构造带项目链接的正式模板简历，用于验证链接行展示。
function buildFormalProjectLinksResumeResponse() {
  const resume = buildResumeResponse()
  return {
    ...resume,
    layout_config: {
      density: 'normal',
      moduleOrder: ['personal', 'summary', 'education', 'work', 'projects', 'skills'],
      visibleModules: ['personal', 'education', 'work', 'projects'],
      spacingScale: 1,
      templateStyle: 'formal',
    },
    content: {
      ...resume.content,
      projects: [{
        name: 'Chat Resume - AI驱动的求职辅导平台',
        overview: 'AI 求职辅导平台，集成 MCP 搜索与语音交互，实现简历诊断与模拟面试。',
        github_url: 'https://github.com/849261680/chat-resume',
        demo_url: 'https://chatresume.tech',
        highlights: [
          { text: 'Prompt Chain：设计 Prompt Chain 解析非结构化简历为 JSON' },
        ],
      }],
    },
  }
}

// 构造 emerald 模板下容易触发页尾裁切的简历内容。
function buildEmeraldClippingResumeResponse() {
  const resume = buildResumeResponse()
  return {
    ...resume,
    layout_config: {
      density: 'custom',
      moduleOrder: ['personal', 'summary', 'education', 'work', 'projects', 'skills'],
      visibleModules: ['personal', 'education', 'work', 'projects'],
      spacingScale: 0.65,
      templateStyle: 'emerald',
    },
    content: {
      ...resume.content,
      personal_info: {
        name: '彭世雄',
        email: '849261680@qq.com',
        phone: '13800138000',
        position: 'Agent开发工程师',
        github: 'https://github.com/849261680',
        photo_url: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==',
        links: [{ id: 'link_7ac48d7ae543', label: 'GitHub', url: 'https://github.com/849261680' }],
      },
      education: [{
        school: '东北大学（985）',
        degree: '本科',
        major: '信息安全',
        duration: '2020-2024',
        highlights: [{ text: '主要课程：计算机组成原理、计算机网络、数据结构与算法、计算机操作系统' }],
      }],
      work_experience: [{
        company: '世优(北京)科技股份有限公司',
        position: 'AI Agent开发工程师',
        duration: '2025/08 - 2025/11',
        highlights: [
          { text: 'Agent 架构：设计 SDR 场景 AI Agent，基于 ToolRegistry + CoreToolScheduler 实现工具注册、调度与状态跟踪，集成 Gemini Function Calling + MCP 接入 CRM，实现线索拉取到沉淀全流程自动化' },
          { text: '工作流自动化：设计工作流自动化模块，支持定时/即时任务与向量化检索，通过 WebSocket 实时推送执行状态，日均处理数百条线索' },
          { text: 'Memory + RAG：建设 Memory 系统与 RAG 检索链路：设计 episodic / semantic / resource / knowledge_vault 四层记忆分类，基于 pgvector + BGE-M3 + BM25 混合检索实现客户信息语义召回，通过 clue_id 绑定线索上下文' },
          { text: 'Prompt 工程：设计销售场景 Prompt Chain 与 Few-shot 示例，约束通话处理的工具调用顺序与结构化输出格式，确保 Agent 行为可控、输出合规' },
        ],
      }],
      projects: [
        {
          name: 'Chat Resume - AI驱动的求职辅导平台',
          overview: 'AI 求职辅导平台，集成 MCP 搜索与语音交互，实现简历诊断与模拟面试。',
          technologies: ['MCP', '大模型', '语音识别', '语音合成'],
          github_url: 'https://github.com/849261680/chat-resume',
          demo_url: 'https://chatresume.tech',
          links: [
            { id: 'link_1195edf6115f', label: 'GitHub', url: 'https://github.com/849261680/chat-resume' },
            { id: 'link_82069664babc', label: 'Demo', url: 'https://chatresu.vercel.app' },
          ],
          highlights: [
            { text: 'Prompt Chain：设计 Prompt Chain 解析非结构化简历为 JSON，结合 JD 关键词匹配与用户记忆，实现简历诊断、岗位差距分析与模拟面试全流程' },
            { text: 'ReAct Agent：设计 ReAct Agent，基于简历 JSON + JD + 用户记忆自主决策工具调用，实现诊断→改写→diff 预览→确认→写回闭环' },
            { text: '安全机制：实现 Human-in-the-loop 确认门：写入型工具先 dry-run 生成结构化 diff，用户确认后才写入，拒绝则终止修改，杜绝大模型幻觉覆盖用户真实经历' },
            { text: '流式工程：建设 SSE 流式事件与 Session Store：将 Agent 文本、工具调用、diff 预览、确认结果序列化为事件并持久化，支持前端断线后通过 Last-Event-ID 恢复事件流' },
          ],
        },
        {
          name: 'Deep Research Agent - 深度研究智能体',
          overview: '基于 LangChain ReAct 的自主研究 Agent，实现 Planning → Tool Use 闭环，支持多轮调研并生成研究报告。',
          technologies: ['LangChain', 'ReAct', 'Tavily Search API'],
          github_url: 'https://github.com/849261680/research-gpt',
          demo_url: 'https://rsgpt.vercel.app',
          links: [
            { id: 'link_7d5a2e8a603b', label: 'GitHub', url: 'https://github.com/849261680/research-gpt' },
            { id: 'link_652262a869e0', label: 'Demo', url: 'https://rsgpt.vercel.app' },
          ],
          highlights: [
            { text: '工作流编排：使用 LangGraph StateGraph 编排顶层工作流与子图递归深挖，实现 Planning → Tool Use → Evidence → Report 完整闭环' },
            { text: '递归深挖：设计递归深挖机制：每个子查询完成后基于压缩证据与校验结果判断证据缺口，自动生成后续查询继续搜索，由深度/广度参数控制成本边界' },
            { text: '证据链校验：建设证据链校验机制：统一管理来源证据，生成报告后自动抽取 claims 并校验引用有效性，结合 LLM 语义判断断言支持度，量化输出报告质量指标' },
            { text: '可观测性：实现 SSE 流式推送研究进度，建设 CostTracker 与 ResearchMetrics 记录 token、搜索次数、来源数量与耗时，使长任务研究过程可观测' },
          ],
        },
      ],
    },
  }
}

// 检查指定文本是否真正出现在预览页可视边界内。
async function findVisiblePreviewText(page: Page, text: string) {
  return page.evaluate((targetText) => {
    const pages = Array.from(document.querySelectorAll('#resume-export-content .resume-page'))
    const elements = Array.from(document.querySelectorAll('#resume-export-content .resume-page li, #resume-export-content .resume-page p'))
      .filter((element) => element.textContent?.includes(targetText))

    return {
      pageCount: pages.length,
      matchCount: elements.length,
      visible: elements.some((element) => {
        const rect = element.getBoundingClientRect()
        const pageElement = element.closest('.resume-page')
        const pageRect = pageElement?.getBoundingClientRect()
        if (!pageRect) return false
        return rect.top >= pageRect.top && rect.bottom <= pageRect.bottom
      }),
    }
  }, text)
}

// 读取当前预览生成的纸张页数。
async function getPreviewPageCount(page: Page) {
  return page.locator('#resume-export-content .resume-page').count()
}

// 读取首个预览页当前屏幕宽度。
async function getFirstPreviewPageWidth(page: Page) {
  return page.evaluate(() => {
    const pageElement = document.querySelector('#resume-export-content .resume-page')
    return pageElement?.getBoundingClientRect().width || 0
  })
}

// 检查要点前缀是否被语义化加粗。
async function hasBoldPreviewLeadLabel(page: Page, label: string) {
  return page.evaluate((targetLabel) => {
    const strongElements = Array.from(document.querySelectorAll('#resume-export-content strong'))
    return strongElements.some((element) => element.textContent === targetLabel)
  }, label)
}

// 检查正式模板项目链接是否为单行而不是列表。
async function getFormalProjectLinkShape(page: Page) {
  return page.evaluate(() => {
    const linkText = 'Demo: https://chatresume.tech | GitHub: https://github.com/849261680/chat-resume'
    const paragraphs = Array.from(document.querySelectorAll('#resume-export-content p'))
    const listItems = Array.from(document.querySelectorAll('#resume-export-content li'))
    const anchors = Array.from(document.querySelectorAll('#resume-export-content p a'))
    return {
      hasOneLineText: paragraphs.some((element) => element.textContent === linkText),
      listItemCount: listItems.filter((element) =>
        element.textContent?.startsWith('Demo:') ||
        element.textContent?.startsWith('GitHub:')
      ).length,
      hrefs: anchors.map((element) => (element as HTMLAnchorElement).href),
    }
  })
}

// 读取首个预览页最后一行到底部边距线的未缩放留白。
async function measureFirstPageBottomGap(page: Page) {
  return page.evaluate(() => {
    const pageElement = document.querySelector('#resume-export-content .resume-page')
    const lineElements = Array.from(document.querySelectorAll('#resume-export-content .resume-page [data-line-index]'))
    if (!pageElement || lineElements.length === 0) return 0

    const pageRect = pageElement.getBoundingClientRect()
    const previewScale = pageRect.width / 794
    const paddingBottom = Number.parseFloat(window.getComputedStyle(pageElement).paddingBottom || '0')
    const lastLineBottom = Math.max(...lineElements.map(element => element.getBoundingClientRect().bottom))
    return (pageRect.bottom - lastLineBottom) / previewScale - paddingBottom
  })
}

test('切换简历样式时预览不会先放大再缩回', async ({ page }) => {
  await mockEditorApis(page)
  await page.goto('/zh/resume/123/edit')

  const pageSheet = page.locator('#resume-export-content .resume-page').first()
  await expect(pageSheet).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)
  const beforeBox = await pageSheet.boundingBox()
  expect(beforeBox?.width).toBeGreaterThan(0)

  await page.evaluate(() => {
    const samples: number[] = []
    Object.assign(window, { __resumePageWidthSamples: samples })
    const sample = () => {
      const pageElement = document.querySelector('#resume-export-content .resume-page')
      if (pageElement) {
        samples.push(pageElement.getBoundingClientRect().width)
      }
      if (samples.length < 90) requestAnimationFrame(sample)
    }
    requestAnimationFrame(sample)
  })

  await page.getByRole('button', { name: '简历设置' }).click()
  await page.getByRole('button', { name: '正式黑白' }).click()
  await page.waitForFunction(() => (window as unknown as { __resumePageWidthSamples?: number[] }).__resumePageWidthSamples?.length === 90)

  const samples = await page.evaluate(() => (window as unknown as { __resumePageWidthSamples: number[] }).__resumePageWidthSamples)
  const maxWidth = Math.max(...samples)
  expect(maxWidth).toBeLessThan((beforeBox?.width || 0) * 1.05)
})

test('绿页眉样式卡片展示绿色页眉缩略预览', async ({ page }) => {
  await mockEditorApis(page)
  await page.goto('/zh/resume/123/edit')

  await page.getByRole('button', { name: '简历设置' }).click()
  const emeraldOption = page.getByRole('button', { name: '绿页眉' })
  await expect(emeraldOption.locator('[data-testid="template-preview-header"]')).toHaveCSS('background-color', 'rgb(5, 150, 105)')
})

test('正式模板项目链接展示为一行', async ({ page }) => {
  await mockEditorApis(page, buildFormalProjectLinksResumeResponse())
  await page.goto('/zh/resume/123/edit')

  await expect(page.locator('#resume-export-content')).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)

  const shape = await getFormalProjectLinkShape(page)
  expect(shape.hasOneLineText).toBe(true)
  expect(shape.listItemCount).toBe(0)
  expect(shape.hrefs).toContain('https://chatresume.tech/')
  expect(shape.hrefs).toContain('https://github.com/849261680/chat-resume')
})

test('经典模板项目描述带标签且不显示关键要点标题', async ({ page }) => {
  await mockEditorApis(page, buildSmartFitResumeResponse())
  await page.goto('/zh/resume/123/edit')

  await expect(page.locator('#resume-export-content')).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)
  await expect(page.locator('#resume-export-content')).toContainText('项目描述：AI 驱动的求职辅导平台')
  await expect(page.locator('#resume-export-content').getByText('关键要点:')).toHaveCount(0)
  await expect(page.locator('#resume-export-content').getByText('项目描述：AI 驱动的求职辅导平台', { exact: false })).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('项目描述：')).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('实现流式对话、差异审阅和一键采纳', { exact: false })).toHaveCSS('color', 'rgb(17, 24, 39)')
})

test('经典模板工作经历文字使用深色', async ({ page }) => {
  await mockEditorApis(page, buildSmartFitResumeResponse())
  await page.goto('/zh/resume/123/edit')

  await expect(page.locator('#resume-export-content')).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)
  await expect(page.locator('#resume-export-content').getByText('前端工程师')).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('2022-至今')).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('负责简历编辑器、实时预览和导出链路', { exact: false })).toHaveCSS('color', 'rgb(17, 24, 39)')
})

test('经典模板教育经历文字使用深色', async ({ page }) => {
  await mockEditorApis(page, buildEmeraldClippingResumeResponse())
  await page.goto('/zh/resume/123/edit')

  await page.getByRole('button', { name: '简历设置' }).click()
  await page.getByRole('button', { name: '经典' }).click()
  await page.mouse.click(20, 20)
  await expect(page.locator('#resume-export-content')).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)
  await expect(page.locator('#resume-export-content').getByText('信息安全 · 本科')).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('2020-2024')).toHaveCSS('color', 'rgb(17, 24, 39)')
  await expect(page.locator('#resume-export-content').getByText('主要课程：计算机组成原理', { exact: false })).toHaveCSS('color', 'rgb(17, 24, 39)')
})

test('智能一页后不同模板的底部留白保持接近', async ({ page }) => {
  test.setTimeout(60_000)
  await mockEditorApis(page, buildSmartFitResumeResponse())
  const templates = [
    { id: 'classic', label: '经典' },
    { id: 'modern', label: '现代' },
    { id: 'formal', label: '正式黑白' },
  ]
  const gaps: number[] = []

  for (const template of templates) {
    await page.goto('/zh/resume/123/edit')
    await page.evaluate(() => window.localStorage.removeItem('resume_layout_123'))
    await page.reload()
    await expect(page.locator('#resume-export-content')).toBeVisible()

    if (template.id !== 'classic') {
      await page.getByRole('button', { name: '简历设置' }).click()
      await page.getByRole('button', { name: template.label }).click()
      await page.mouse.click(20, 20)
    }

    const smartFitButton = page.locator('button[title="自动调整间距使简历恰好一页"]')
    await smartFitButton.click()
    await expect(smartFitButton).toBeEnabled({ timeout: 20_000 })
    await expect(page.locator('#resume-export-content .resume-page')).toHaveCount(1)
    gaps.push(await measureFirstPageBottomGap(page))
  }

  expect(Math.max(...gaps) - Math.min(...gaps)).toBeLessThanOrEqual(32)
  for (const gap of gaps) {
    expect(Math.abs(gap - SMART_FIT_TARGET_BOTTOM_GAP)).toBeLessThanOrEqual(SMART_FIT_GAP_TOLERANCE)
  }
})

test('绿页眉样式不会裁掉页尾项目要点', async ({ page }) => {
  await page.setViewportSize({ width: 2048, height: 768 })
  await mockEditorApis(page, buildEmeraldClippingResumeResponse())
  await page.goto('/zh/resume/123/edit')

  await expect(page.locator('#resume-export-content')).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)

  const result = await findVisiblePreviewText(page, '可观测性：实现 SSE 流式推送研究进度')
  expect(await getFirstPreviewPageWidth(page)).toBeGreaterThan(600)
  expect(await getPreviewPageCount(page)).toBeGreaterThan(1)
  expect(result.matchCount).toBeGreaterThan(0)
  expect(result.visible).toBe(true)
  expect(await hasBoldPreviewLeadLabel(page, 'Prompt Chain：')).toBe(true)
})
