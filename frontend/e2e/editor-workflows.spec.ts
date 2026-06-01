/**
 * 编辑页工作流端到端测试
 *
 * 用于补齐上传、导出 PDF 和面试工作台的关键前端链路验证。
 */

import { expect, test, Page } from '@playwright/test'
import fs from 'node:fs/promises'

import { registerUser, uniqueEmail } from './helpers'

/**
 * 注册新用户并等待进入 dashboard，供编辑页相关场景复用。
 */
// 用于登录as。
async function loginAs(page: Page, email: string) {
  await registerUser(page, email)
  await page.waitForURL('**/dashboard', { timeout: 12_000 })
}

/**
 * 从仪表板创建空白简历并返回新建后的简历 ID。
 */
// 用于创建简历from仪表盘。
async function createResumeFromDashboard(page: Page, email: string): Promise<string> {
  await loginAs(page, email)
  await page.getByRole('button', { name: '新建简历' }).click()
  await page.waitForURL(/\/resume\/\d+\/edit/, { timeout: 12_000 })
  const resumeId = page.url().match(/\/resume\/(\d+)\/edit/)?.[1]
  expect(resumeId, '点击新建简历后应进入编辑页').toBeTruthy()
  return resumeId as string
}

/**
 * 构造一份最小可用的简历响应体，供上传和面试页面复用。
 */
// 用于处理build简历响应。
function buildResumeResponse(id: number) {
  return {
    id,
    title: '测试简历',
    owner_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    content: {
      parsing_quality: 0,
      parsing_method: 'fallback',
      job_application: { target_company: '测试公司', target_title: '前端工程师', jd_text: '负责前端开发' },
      personal_info: { name: '测试用户', email: 'e2e@test.example' },
      education: [],
      work_experience: [],
      skills: [],
      projects: [],
    },
  }
}

/**
 * 为编辑页安装最小登录态和 API mock，避免测试依赖真实账号注册。
 */
// 用于处理install编辑器APImock。
async function installEditorApiMock(
  page: Page,
  resume = buildResumeResponse(123),
  chatMessages: Array<{ id: number; role: 'user' | 'assistant'; content: string; stream_events?: unknown[] | null }> = [],
  pendingConfirmation: Record<string, unknown> = {
    session_id: null,
    status: 'idle',
    pending_action: null,
  }
) {
  const user = {
    id: 1,
    email: 'editor@test.example',
    is_active: true,
    created_at: new Date().toISOString(),
  }

  await page.addInitScript((storedUser) => {
    window.localStorage.setItem('auth_user', JSON.stringify(storedUser))
  }, user)
  await page.context().addCookies([
    {
      name: 'refresh_token',
      value: 'test-refresh-token',
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      sameSite: 'Lax',
    },
    {
      name: 'NEXT_LOCALE',
      value: 'zh',
      domain: 'localhost',
      path: '/',
      sameSite: 'Lax',
    },
  ])

  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    })
  })
  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ token_type: 'bearer', user }),
    })
  })
  await page.route(`**/api/resumes/${resume.id}/chat-messages`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(chatMessages),
    })
  })
  await page.route('**/api/ai/chat/pending-confirmation**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(pendingConfirmation),
    })
  })
  await page.route(`**/api/resumes/${resume.id}/layout`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })
  await page.route(`**/api/resumes/${resume.id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(resume),
    })
  })
}

/**
 * 在浏览器里注入一个可控的 Resume Agent mock，用于真实驱动流式 diff 确认交互。
 */
// 用于处理install简历agentmock。
async function installResumeAgentMock(
  page: Page,
  options: {
    pauseAfterToolCall?: boolean
    extraDiffItemCount?: number
    includeEmptyBeforeDiff?: boolean
    omitDiffItems?: boolean
  } = {}
) {
  await page.addInitScript(({ pauseAfterToolCall, extraDiffItemCount, includeEmptyBeforeDiff, omitDiffItems }) => {
    const originalFetch = window.fetch.bind(window)
    const diffSummaryLines = [
      '改前：负责前端开发',
      '改后：主导前端重构，首屏加载提速 35%',
      '改动理由：补充量化结果',
    ]
    if (includeEmptyBeforeDiff) {
      diffSummaryLines.push('改前：空', '改后：腾讯', '改动理由：用户明确要求投递腾讯公司 Agent 开发岗')
    }
    const diffSummary = diffSummaryLines.join('\n')
    const skillBefore = JSON.stringify({
      _id: 'skill_c10dbc140337',
      category: '编程语言',
      items: ['Python'],
    })
    const skillAfter = JSON.stringify({
      _id: 'skill_c10dbc140337',
      category: '编程语言',
      items: ['Python', 'TypeScript', 'FastAPI', 'Next.js'],
    })
    const unchangedSkill = JSON.stringify({
      id: 'skill_same_json',
      category: '编程语言',
      items: ['Python', 'TypeScript', 'FastAPI', 'Next.js'],
    })
    const truncatedSkillBefore = '{"id": "skill_truncated_json", "category": "Agent 技术栈", "items": ["LangChain", "Few-…'
    const truncatedSkillAfter = '{"id": "skill_truncated_json", "category": "Agent 技术栈", "items": ["LangChain", "MCP"]'
    const textFieldBefore = JSON.stringify({
      id: 'bullet_text_json',
      text: '集成Tavily Search API实现联网搜索',
    })
    const textFieldAfter = JSON.stringify({
      id: 'bullet_text_json',
      text: '集成 Tavily Search API 实现实时联网搜索，为研究报告提供多源、时效性强的信息支撑，确保输出内容的准确性和时效性',
    })
    const newBulletAfter = JSON.stringify({
      id: 'work_new_json',
      text: '在提示词中引入 few-shot 策略，针对销售场景中的特定任务优化 Agent 输出质量，提升任务完成准确率',
    })
    const baseDiffItems = [
      {
        before: '负责前端开发',
        after: '主导前端重构，首屏加载提速 35%',
        reason: '补充量化结果',
      },
      {
        before: skillBefore,
        after: skillAfter,
        reason: '补充简历中已体现的编程语言和框架',
      },
      {
        before: unchangedSkill,
        after: unchangedSkill,
        reason: '精简技能列表，去掉与 Agent 开发核心不直接相关的条目',
      },
      {
        before: truncatedSkillBefore,
        after: truncatedSkillAfter,
        reason: '精简：Few-shot Prompting 并入 Context Engineering',
      },
      {
        before: textFieldBefore,
        after: textFieldAfter,
        reason: '补充联网搜索对研究报告质量和时效性的价值',
      },
      {
        before: '（新增）',
        after: newBulletAfter,
        reason: '拆分 few-shot 策略为独立 bullet 并突出任务表现提升',
      },
    ]
    if (includeEmptyBeforeDiff) {
      baseDiffItems.push({
        before: '空',
        after: '腾讯',
        reason: '用户明确要求投递腾讯公司 Agent 开发岗',
      })
    }
    const extraDiffItems = Array.from({ length: extraDiffItemCount || 0 }, (_, index) => ({
      before: `自动滚动验证项 ${index} 改前`,
      after: `自动滚动验证项 ${index} 改后`,
      reason: `自动滚动验证项 ${index} 原因`,
    }))
    const diffItems = [...baseDiffItems, ...extraDiffItems]
    const serializedDiffItems = omitDiffItems ? undefined : diffItems

    ;(window as Window & {
      __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean; feedback?: string }>
      __resumeAgentResolve?: (decision: { confirmed: boolean; feedback?: string }) => void
      __resumeAgentContinueAfterToolCall?: () => void
    }).__resumeAgentConfirmCalls = []

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestUrl =
        typeof input === 'string'
          ? input
          : input instanceof Request
            ? input.url
            : input.toString()
      const method = (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase()

      if (requestUrl.includes('/chat-messages')) {
        return new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (requestUrl.includes('/api/ai/chat/confirm-tool')) {
        const payload = init?.body && typeof init.body === 'string'
          ? JSON.parse(init.body)
          : { confirmed: false }
        const runtimeWindow = window as Window & {
          __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean; feedback?: string }>
          __resumeAgentResolve?: (decision: { confirmed: boolean; feedback?: string }) => void
        }
        runtimeWindow.__resumeAgentConfirmCalls?.push(payload)
        runtimeWindow.__resumeAgentResolve?.({
          confirmed: Boolean(payload.confirmed),
          feedback: typeof payload.feedback === 'string' ? payload.feedback : undefined,
        })

        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (requestUrl.includes('/api/ai/chat/stream')) {
        const encoder = new TextEncoder()
        const stream = new ReadableStream({
          // 用于处理start。
          async start(controller) {
            const runtimeWindow = window as Window & {
              __resumeAgentResolve?: (decision: { confirmed: boolean; feedback?: string }) => void
              __resumeAgentContinueAfterToolCall?: () => void
            }
            const decision = new Promise<{ confirmed: boolean; feedback?: string }>((resolve) => {
              runtimeWindow.__resumeAgentResolve = resolve
            })
            // 用于处理pushevent。
            const pushEvent = (payload: Record<string, unknown>) => {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`))
            }
            // 用于处理sleep。
            const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

            pushEvent({ session_id: 'resume_session_e2e', content: '', done: false })
            await sleep(50)
            pushEvent({ content: '我建议先强化项目结果表达。', done: false })
            await sleep(50)
            pushEvent({
              event_type: 'tool_call',
              tool_call_started: true,
              call_id: 'call_e2e',
              tool_id: 'update_bullet',
              tool_name: '优化项目经历',
              tool_display_name: '优化项目经历',
              tool_input: { section: 'projects', item_id: 'proj_1' },
              display_message: '正在调用 update_bullet',
              done: false,
            })
            if (pauseAfterToolCall) {
              await new Promise<void>((resolve) => {
                runtimeWindow.__resumeAgentContinueAfterToolCall = resolve
              })
            }
            await sleep(50)
            pushEvent({
              event_type: 'tool_pending',
              tool_pending: true,
              call_id: 'call_e2e',
              tool_name: '优化项目经历',
              tool_display_name: '优化项目经历',
              diff_summary: diffSummary,
              diff_items: serializedDiffItems,
              done: false,
            })

            const { confirmed, feedback } = await decision
            await sleep(50)
            pushEvent({
              [confirmed ? 'tool_confirmed' : 'tool_rejected']: true,
              call_id: 'call_e2e',
              tool_name: '优化项目经历',
              tool_display_name: '优化项目经历',
              diff_summary: diffSummary,
              diff_items: serializedDiffItems,
              done: false,
            })
            await sleep(50)
            pushEvent({
              content: confirmed
                ? '已应用修改。'
                : feedback
                  ? '已按反馈重新生成修改。'
                  : '已保留原文。',
              done: false,
            })
            await sleep(30)
            pushEvent({ done: true })
            controller.close()
          },
        })

        return new Response(stream, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }

      return originalFetch(input, init)
    }
  }, options)
}

/**
 * 读取浏览器侧记录下来的确认请求，验证用户点击是否真的发出了对应确认结果。
 */
// 用于处理read简历agentconfirmcalls。
async function readResumeAgentConfirmCalls(page: Page) {
  return page.evaluate(() => {
    const runtimeWindow = window as Window & {
      __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean; feedback?: string }>
    }
    return runtimeWindow.__resumeAgentConfirmCalls || []
  })
}

/**
 * 读取包含指定文本的最近滚动容器指标，用于验证真实页面滚动行为。
 */
// 用于读取文本所在滚动容器指标。
async function readNearestScrollMetrics(page: Page, text: string) {
  return page.evaluate((targetText) => {
    const candidates = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .filter((element) => element.textContent?.includes(targetText))
    const target = candidates.find((element) =>
      !Array.from(element.children).some((child) => child.textContent?.includes(targetText))
    ) || candidates[0]
    let element = target || null
    while (element) {
      const style = window.getComputedStyle(element)
      const canScroll = style.overflowY === 'auto' || style.overflowY === 'scroll'
      if (canScroll && element.scrollHeight > element.clientHeight) {
        return {
          scrollTop: element.scrollTop,
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          distanceFromBottom: element.scrollHeight - element.scrollTop - element.clientHeight,
        }
      }
      element = element.parentElement
    }
    return null
  }, text)
}

/**
 * 在预览页内选中一段可见文本，复用浏览器原生 Selection 触发浮动工具条。
 */
// 用于选择简历previewtext。
async function selectResumePreviewText(page: Page, text: string) {
  const resumePage = page.locator('.resume-page:not(.invisible)').first()
  await expect(resumePage).toContainText(text)
  const selectedTextElement = resumePage.getByText(text, { exact: true })
  await expect(selectedTextElement).toBeVisible()
  const selectedText = await selectedTextElement.evaluate((targetElement) => {
    const range = document.createRange()
    range.selectNodeContents(targetElement)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    const selectedText = selection?.toString() || ''
    document.querySelector('main')?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    return selectedText
  })
  expect(selectedText).toContain(text)
}

/** 在聊天消息区域选中一段可见文本，触发与预览区一致的浮动按钮。 */
// 用于选择聊天消息text。
async function selectChatMessageText(page: Page, text: string) {
  await expect(page.locator('.agent-panel')).toContainText(text)
  const selectedText = await page.evaluate((targetText) => {
    const targetElement = Array.from(document.querySelectorAll<HTMLElement>('.agent-panel p'))
      .find((element) => {
        const rect = element.getBoundingClientRect()
        return element.textContent?.includes(targetText) && rect.width > 0 && rect.height > 0
      })
    if (!targetElement) return ''
    const range = document.createRange()
    range.selectNodeContents(targetElement)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    const selectedText = selection?.toString() || ''
    document.querySelector('main')?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    return selectedText
  }, text)
  expect(selectedText).toContain(text)
}

/** 读取聊天选区高亮和目标文本的视口位置差，用于验证滚动后仍贴合。 */
// 用于读取聊天选区高亮alignment。
async function readChatSelectionHighlightAlignment(page: Page, text: string) {
  return page.evaluate((targetText) => {
    const targetElement = Array.from(document.querySelectorAll<HTMLElement>('.agent-panel p'))
      .find((element) => {
        const rect = element.getBoundingClientRect()
        return element.textContent?.includes(targetText) && rect.width > 0 && rect.height > 0
      })
    const highlight = document.querySelector<HTMLElement>('[data-testid="chat-selection-highlight"]')
    const messages = document.querySelector<HTMLElement>('[data-testid="resume-chat-messages"]')
    if (!targetElement || !highlight || !messages) return null
    const targetRect = targetElement.getBoundingClientRect()
    const highlightRect = highlight.getBoundingClientRect()
    return {
      topDelta: Math.round((highlightRect.top - targetRect.top) * 10) / 10,
      scrollTop: messages.scrollTop,
    }
  }, text)
}

/**
 * 用真实鼠标拖拽选中多条预览内容，覆盖用户手动跨行选区的交互路径。
 */
// 用于处理dragselect简历previewtext。
async function dragSelectResumePreviewText(page: Page, startText: string, endText: string) {
  const resumePage = page.locator('.resume-page:not(.invisible)').first()
  const start = resumePage.getByText(startText, { exact: true })
  const end = resumePage.getByText(endText, { exact: true })
  await expect(start).toBeVisible()
  await expect(end).toBeVisible()

  const selectedText = await resumePage.evaluate((rootElement, texts) => {
    const findVisibleElement = (targetText: string) => Array.from(rootElement.querySelectorAll<HTMLElement>('*'))
      .find((element) => {
        const rect = element.getBoundingClientRect()
        return element.textContent === targetText && rect.width > 0 && rect.height > 0
      })
    const startElement = findVisibleElement(texts.startText)
    const endElement = findVisibleElement(texts.endText)
    if (!startElement || !endElement) return ''
    const range = document.createRange()
    range.setStartBefore(startElement)
    range.setEndAfter(endElement)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    const selectedText = selection?.toString() || ''
    document.querySelector('main')?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    return selectedText
  }, { startText, endText })
  expect(selectedText).toContain(startText.slice(0, 8))
}

/**
 * 读取预览区选区相关的全部视觉状态，避免只清掉原生 Selection 却漏掉自定义高亮。
 */
// 用于处理read简历selectionvisualstate。
async function readResumeSelectionVisualState(page: Page) {
  return page.evaluate(() => {
    const highlightRegistry = CSS as typeof CSS & {
      highlights?: { has?: (name: string) => boolean }
    }
    return {
      selectedText: window.getSelection()?.toString() || '',
      hasCustomHighlight: Boolean(highlightRegistry.highlights?.has?.('resume-preview-selection')),
      drawnHighlightCount: document.querySelectorAll('[data-testid="resume-selection-highlight"]').length,
    }
  })
}

/**
 * 判断指定 value 的输入框是否实际落在浏览器可视区域内。
 */
// 用于检查输入框是否可见in viewport。
async function isInputValueInViewport(page: Page, value: string) {
  return page.evaluate((targetValue) => {
    const input = Array.from(document.querySelectorAll<HTMLInputElement>('input'))
      .find((element) => element.value === targetValue)
    if (!input) return false
    const rect = input.getBoundingClientRect()
    return rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth
  }, value)
}

/**
 * 读取指定 value 输入框的位置，用于把鼠标放到真实编辑区内触发滚动。
 */
// 用于读取输入框位置。
async function inputValueBox(page: Page, value: string) {
  return page.evaluate((targetValue) => {
    const input = Array.from(document.querySelectorAll<HTMLInputElement>('input'))
      .find((element) => element.value === targetValue)
    if (!input) return null
    const rect = input.getBoundingClientRect()
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
  }, value)
}

/**
 * 等待指定 value 的输入框实际进入浏览器可视区域。
 */
// 用于等待输入框进入viewport。
async function expectInputValueInViewport(page: Page, value: string) {
  await expect.poll(() => isInputValueInViewport(page, value)).toBe(true)
}

test.describe('编辑页工作流', () => {
  test('路由 ID 无效时不会请求 NaN 简历接口', async ({ page }) => {
    const invalidResumeApiCalls: string[] = []

    await installEditorApiMock(page, buildResumeResponse(123))
    await page.route('**/api/resumes/NaN**', async (route) => {
      invalidResumeApiCalls.push(route.request().url())
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: [{ msg: 'invalid integer' }] }),
      })
    })
    await page.route('**/api/resumes/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
    })

    await page.goto('/zh/resume/NaN/edit')
    await page.waitForURL('**/dashboard', { timeout: 12_000 })

    expect(invalidResumeApiCalls).toEqual([])
  })

  test('选中预览内容后可以粘贴到聊天输入框', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')

    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()
    await page.getByRole('button', { name: '添加至对话框' }).click()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
    const chatInputBox = page.getByTestId('resume-chat-input-box')
    await expect(chatInputBox.getByTestId('selected-resume-context')).toContainText('负责前端开发与性能优化')
    const chatInput = page.getByPlaceholder('输入消息...')
    await expect(chatInput).toBeFocused()
    await chatInput.press('Backspace')
    await expect(chatInputBox.getByTestId('selected-resume-context')).toBeHidden()
    await expect(chatInput).toBeFocused()
  })

  test('选中聊天内容后可以粘贴到聊天输入框', async ({ page }) => {
    const chatText = 'Agent 建议保留 RAG 项目经验'
    await installEditorApiMock(page, buildResumeResponse(123), [
      {
        id: 1,
        role: 'assistant',
        content: chatText,
      },
    ])

    await page.goto('/zh/resume/123/edit')
    await selectChatMessageText(page, chatText)

    await expect(page.getByRole('button', { name: '添加至对话框' })).toBeVisible()
    await expect(page.getByTestId('chat-selection-highlight').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '快速优化' })).toBeHidden()
    await page.getByRole('button', { name: '添加至对话框' }).click()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
    await expect(page.getByTestId('chat-selection-highlight')).toHaveCount(0)
    const chatInputBox = page.getByTestId('resume-chat-input-box')
    await expect(chatInputBox.getByTestId('selected-resume-context')).toContainText(chatText)
    await expect(page.getByPlaceholder('输入消息...')).toBeFocused()
  })

  test('跨多段聊天内容复制时使用缓存选区全文', async ({ page }) => {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
    const chatText = [
      '# 综合 JD：AGENT 开发工程师（普适版）',
      '',
      '基于 12 条 JD（畅捷通 ×2、美团、京东、耳朵时间、智谱华章、星河觉醒、思格涡野 ×2、普适版 ×3）的综合提炼。',
      '',
      '---',
      '',
      '## 一、核心能力要求（4 家高频重叠）',
      '',
      '### 1. Agent 架构设计与落地',
      '',
      '- 独立完成 Planning → Tool Use → Memory → Multi-Agent 完整闭环',
      '- 熟悉 Agentic 架构：Function Calling、ReAct、Prompt Chain',
      '- 有可交互的 AI 项目 Demo 成果',
      '',
      '### 2. 技术栈',
      '',
      '- Python 精通（Pandas/NumPy + 高级特性）',
      '- Agent 框架：LangChain / LlamaIndex / OpenClaw / Dify / Coze',
      '- LLM：GPT-4、千问、Kimi 等主流模型 API 调用',
      '- Prompt Engineering：Few-shot、Prompt Chain 设计与优化',
    ].join('\n')
    await installEditorApiMock(page, buildResumeResponse(123), [
      {
        id: 1,
        role: 'assistant',
        content: chatText,
      },
    ])

    await page.goto('/zh/resume/123/edit')
    await expect(page.locator('.agent-panel')).toContainText('Prompt Engineering')
    await page.evaluate(async () => {
      const root = document.querySelector<HTMLElement>('.agent-panel .markdown-content')
      const firstElement = root?.querySelector('h1')
      const lastElement = Array.from(root?.querySelectorAll('li') || []).at(-1)
      if (!root || !firstElement || !lastElement) return ''

      const range = document.createRange()
      range.setStartBefore(firstElement)
      range.setEndAfter(lastElement)
      const selection = window.getSelection()
      selection?.removeAllRanges()
      selection?.addRange(range)
      document.querySelector('main')?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    })
    await expect(page.getByRole('button', { name: '添加至对话框' })).toBeVisible()
    await page.evaluate(() => window.focus())
    await page.evaluate(() => navigator.clipboard.writeText('before-copy'))
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+C' : 'Control+C')
    await expect.poll(() => (
      page.evaluate(() => navigator.clipboard.readText())
    )).not.toBe('before-copy')
    const copiedText = await page.evaluate(() => navigator.clipboard.readText())

    expect(copiedText).toContain('1. Agent 架构设计与落地')
    expect(copiedText).toContain('2. 技术栈')
    expect(copiedText).toContain('Prompt Engineering：Few-shot、Prompt Chain 设计与优化')
  })

  test('聊天选区颜色滚动时跟随文本', async ({ page }) => {
    const chatText = 'Agent 建议保留 RAG 项目经验'
    const chatMessages = [
      { id: 1, role: 'assistant' as const, content: chatText },
      ...Array.from({ length: 14 }, (_, index) => ({
        id: index + 2,
        role: 'assistant' as const,
        content: `滚动占位消息 ${index}：用于撑开聊天区域，验证选区高亮跟随文本滚动。`,
      })),
    ]
    await installEditorApiMock(page, buildResumeResponse(123), chatMessages)

    await page.goto('/zh/resume/123/edit')
    const messages = page.getByTestId('resume-chat-messages')
    await messages.evaluate((element) => {
      element.scrollTop = 0
      element.dispatchEvent(new Event('scroll', { bubbles: true }))
    })
    await selectChatMessageText(page, chatText)

    const before = await readChatSelectionHighlightAlignment(page, chatText)
    expect(before).not.toBeNull()
    expect(Math.abs(before!.topDelta)).toBeLessThanOrEqual(2)
    await messages.evaluate((element) => {
      element.scrollTop += 80
      element.dispatchEvent(new Event('scroll', { bubbles: true }))
    })
    const after = await readChatSelectionHighlightAlignment(page, chatText)
    expect(after).not.toBeNull()
    expect(after!.scrollTop).toBeGreaterThan(before!.scrollTop)
    expect(Math.abs(after!.topDelta)).toBeLessThanOrEqual(2)
  })

  test('点击预览区外部会取消选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()

    await page.getByText('简历智能体').click()

    await expect(page.getByRole('button', { name: '快速优化' })).toBeHidden()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
  })

  test('按下预览区外部时会立刻取消选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()

    await page.getByText('简历智能体').dispatchEvent('pointerdown', { bubbles: true })

    await expect(page.getByRole('button', { name: '快速优化' })).toBeHidden()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
  })

  test('快速优化会通过对话框 Agent 发送选区和要求', async ({ page }) => {
    const selectedHighlight = '负责前端开发与性能优化，搭建性能监控指标并定位首屏加载瓶颈，推动组件拆分、资源压缩和缓存策略落地，让核心页面交互更稳定。同时沉淀可复用的优化 checklist，帮助团队在后续迭代中持续发现并修复性能回退问题。'
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: selectedHighlight }],
      },
    ]
    let streamPayload: { message?: string } | null = null
    await installEditorApiMock(page, resume)
    await page.route('**/api/ai/chat/stream', async (route) => {
      const body = route.request().postData()
      streamPayload = body ? JSON.parse(body) : null
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"done":true}\n\n',
      })
    })

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, selectedHighlight)
    await page.getByRole('button', { name: '快速优化' }).click()
    await expect(page.getByTestId('resume-selection-highlight').first()).toBeVisible()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 2,
    })
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await page.getByRole('button', { name: '关闭快速优化' }).click()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })

    await selectResumePreviewText(page, selectedHighlight)
    await page.getByRole('button', { name: '快速优化' }).click()
    await quickEditInput.fill('改得更有结果导向')
    await page.getByRole('button', { name: '发送快速优化' }).click()

    await expect.poll(() => streamPayload?.message || '').toContain(selectedHighlight)
    expect(streamPayload?.message).toContain('改得更有结果导向')
    const quotedContext = page.getByTestId('selected-resume-message-context').last()
    await expect(quotedContext).toBeVisible()
    await expect(quotedContext).toContainText('引用')
    await expect(quotedContext).toContainText('负责前端开发与性能优化')
    await quotedContext.getByText('展开全文').click()
    await expect(quotedContext.getByText('收起')).toBeVisible()
    expect(await quotedContext.evaluate((element) => (
      (element.innerText.match(/负责前端开发与性能优化/g) || []).length
    ))).toBe(1)
    await quotedContext.getByText('收起').click()
    await expect(quotedContext.getByText('展开全文')).toBeVisible()
    await expect(page.getByTestId('selected-resume-message-request').last()).toHaveText('改得更有结果导向')
    await expect(quickEditInput).toBeHidden()
  })

  test('Agent 运行时发送按钮会变成停止并中断 stream', async ({ page }) => {
    const resume = buildResumeResponse(123)
    let streamAbortDetected = false
    await installEditorApiMock(page, resume)
    await page.addInitScript(() => {
      const originalFetch = window.fetch.bind(window)
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const requestUrl =
          typeof input === 'string'
            ? input
            : input instanceof Request
              ? input.url
              : input.toString()
        if (!requestUrl.includes('/api/ai/chat/stream')) {
          return originalFetch(input, init)
        }
        return new Promise<Response>((resolve, reject) => {
          const signal = init?.signal
          signal?.addEventListener('abort', () => {
            ;(window as Window & { __resumeAgentStreamAborted?: boolean }).__resumeAgentStreamAborted = true
            reject(new DOMException('Aborted', 'AbortError'))
          })
          const encoder = new TextEncoder()
          const stream = new ReadableStream({
            // 用于保持 stream 运行直到用户停止。
            start(controller) {
              controller.enqueue(encoder.encode('data: {"session_id":"stop_test","content":"思考中","done":false}\\n\\n'))
            },
          })
          resolve(new Response(stream, {
            status: 200,
            headers: { 'Content-Type': 'text/event-stream' },
          }))
        })
      }
    })

    await page.goto('/zh/resume/123/edit')
    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await page.getByRole('button', { name: '发送消息' }).click()

    const stopButton = page.getByRole('button', { name: '停止 Agent' })
    await expect(stopButton).toBeVisible()
    await expect(page.getByRole('button', { name: '发送消息' })).toHaveCount(0)
    await stopButton.click()

    await expect.poll(() => page.evaluate(() => (
      Boolean((window as Window & { __resumeAgentStreamAborted?: boolean }).__resumeAgentStreamAborted)
    ))).toBe(true)
    streamAbortDetected = await page.evaluate(() => (
      Boolean((window as Window & { __resumeAgentStreamAborted?: boolean }).__resumeAgentStreamAborted)
    ))
    expect(streamAbortDetected).toBe(true)
    await expect(page.getByRole('button', { name: '发送消息' })).toBeVisible()
  })

  test('发送快速优化后会立刻关闭输入框', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    let releaseStream: (() => void) | null = null
    await installEditorApiMock(page, resume)
    await page.route('**/api/ai/chat/stream', async (route) => {
      await new Promise<void>((resolve) => {
        releaseStream = resolve
      })
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"done":true}\n\n',
      })
    })

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await quickEditInput.fill('asd')

    await page.getByRole('button', { name: '发送快速优化' }).click()

    await expect(quickEditInput).toBeHidden()
    releaseStream?.()
  })

  test('按下快速优化关闭按钮会立刻取消选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()

    await page.getByRole('button', { name: '关闭快速优化' }).dispatchEvent('pointerdown', { bubbles: true })

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('关闭快速优化后不会在鼠标释放时恢复选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await page.locator('.resume-page').first().getByText('负责前端开发与性能优化', { exact: true }).evaluate((targetElement) => {
      const range = document.createRange()
      range.selectNodeContents(targetElement)
      ;(window as Window & { __restoreResumeSelection?: () => string }).__restoreResumeSelection = () => {
        const nextSelection = window.getSelection()
        nextSelection?.removeAllRanges()
        nextSelection?.addRange(range.cloneRange())
        return nextSelection?.toString() || ''
      }
    })

    await page.getByRole('button', { name: '关闭快速优化' }).click()
    await expect(page.evaluate(() => (
      (window as Window & { __restoreResumeSelection?: () => string }).__restoreResumeSelection?.() || ''
    ))).resolves.toContain('负责前端开发与性能优化')

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('手动跨行选区关闭快速优化后会清掉选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    const firstHighlight = '基于BOSS直聘MCP实现职位实时搜索，自动生成简历优化建议，打通求职-优化闭环'
    const secondHighlight = '设计专用提示词驱动大模型完成简历结构化解析，准确率显著优于传统规则方法'
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [
          { text: firstHighlight },
          { text: secondHighlight },
          { text: '集成语音识别与合成实现端到端语音交互，高度还原真实面试场景' },
        ],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await dragSelectResumePreviewText(page, firstHighlight, secondHighlight)
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()

    await page.getByRole('button', { name: '关闭快速优化' }).click()

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('智能一页会把不足一页的简历尽量撑满', async ({ page }) => {
    await installEditorApiMock(page, buildResumeResponse(123))

    await page.goto('/zh/resume/123/edit')
    const exportContent = page.locator('#resume-export-content')
    await expect(exportContent).toBeVisible()

    const initialScale = await exportContent.evaluate((element) =>
      Number(getComputedStyle(element).getPropertyValue('--spacing-scale'))
    )
    expect(initialScale).toBe(1)

    await page.getByRole('button', { name: '智能一页' }).click()

    await expect.poll(async () => (
      exportContent.evaluate((element) =>
        Number(getComputedStyle(element).getPropertyValue('--spacing-scale'))
      )
    )).toBeGreaterThan(1)
  })

  test('编辑器长文本输入框会按内容增高', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.education = [
      {
        school: '东北大学',
        major: '信息安全',
        degree: '硕士',
        duration: '2018.09 - 2022.06',
        highlights: [
          {
            text: '主要课程：计算机组成原理、计算机网络、数据结构与算法、计算机操作系统、数据库系统与信息安全工程实践',
          },
        ],
      },
    ]
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '销售智能体工程师',
        duration: '2025',
        highlights: [
          {
            text: '端侧集成 ASR 实现电话录音自动转文本与关键信息抽取，自动生成跟进任务，消除销售通话后的人工整理环节',
          },
        ],
      },
    ]
    resume.content.projects = [
      {
        name: 'Chat Resume',
        role: '全栈工程师',
        duration: '2025',
        overview: 'AI 驱动的求职辅导平台，提供简历诊断、模拟面试、能力评估功能。通过 BOSS 直聘 MCP 工具实时搜索职位并生成简历优化建议。',
        highlights: [
          {
            text: '的',
          },
        ],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await page.getByRole('button', { name: '工作' }).click()
    const highlightInput = page.getByPlaceholder('负责后端系统重构，接口平均响应时间下降 35%')
    await expect(highlightInput).toBeVisible()
    expect(await highlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)

    await page.getByRole('button', { name: '项目' }).click()
    const overviewInput = page.getByPlaceholder('一句话说明项目背景、目标或你的角色...')
    const projectHighlightInput = page.getByPlaceholder('实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%')
    await expect(overviewInput).toBeVisible()
    await expect(projectHighlightInput).toBeVisible()
    expect(await overviewInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)
    expect(await projectHighlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)
    expect(await projectHighlightInput.evaluate((element) => element.clientHeight)).toBeLessThanOrEqual(52)

    await page.getByRole('button', { name: '教育' }).click()
    const educationHighlightInput = page.getByPlaceholder('985高校、主要课程、奖项、研究方向等')
    await expect(educationHighlightInput).toBeVisible()
    expect(await educationHighlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)
  })

  test('项目编辑区内容超过面板高度时可以向下滚动', async ({ page }) => {
    await page.setViewportSize({ width: 1124, height: 786 })
    const resume = buildResumeResponse(123)
    resume.content.projects = [
      {
        name: 'Chat Resume - AI驱动的求职辅导',
        role: '前端开发工程师',
        duration: '2023.03 - 2023.08',
        github_url: 'https://github.com/849261680',
        demo_url: 'https://chatresu.vercel.app',
        overview: 'AI驱动的求职辅导平台，提供简历诊断、模拟面试、能力评估功能。技术亮点：能够通过BOSS直聘MCP工具，搜索相关职位信息，并生成简历优化建议；智能简历解析：通过特定提示词，使大模型将简历输出为结构化的json格式，解析准确率优于传统方法；语音交互：集成语音识别和语音合成，打造沉浸式面试体验。',
        highlights: [
          {
            text: '实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%',
          },
        ],
      },
      {
        name: 'Deep Research Agent',
        role: '全栈工程师',
        duration: '2023.09 - 2023.12',
        overview: '第二个项目简介',
        highlights: [
          {
            text: '第二个项目成果',
          },
        ],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await page.getByRole('button', { name: '项目' }).click()
    await expectInputValueInViewport(page, 'Chat Resume - AI驱动的求职辅导')
    expect(await isInputValueInViewport(page, 'Deep Research Agent')).toBe(false)

    const firstProjectBox = await inputValueBox(page, 'Chat Resume - AI驱动的求职辅导')
    expect(firstProjectBox, '第一个项目输入框应可见，才能在左侧编辑区内滚动').toBeTruthy()
    if (!firstProjectBox) return
    await page.mouse.move(firstProjectBox.x + 16, firstProjectBox.y + 16)
    await page.mouse.wheel(0, 900)

    await expectInputValueInViewport(page, 'Deep Research Agent')
  })

  test('上传真实文件后轮询解析任务，完成后进入编辑页并加载简历', async ({ page }) => {
    await loginAs(page, uniqueEmail('uploadflow'))
    const uploadedResume = buildResumeResponse(999)

    await page.route('**/api/upload/resume', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'upload-job-999', status: 'queued' }),
      })
    })
    await page.route('**/api/upload/resume-jobs/upload-job-999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'upload-job-999',
          status: 'completed',
          resume_id: 999,
          error: null,
          original_filename: 'resume.txt',
        }),
      })
    })
    await page.route('**/api/resumes/999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(uploadedResume),
      })
    })
    await page.route('**/api/resumes/999/chat-messages', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
    })

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'resume.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('测试用户\n前端工程师\nOpenAI'),
    })

    await page.waitForURL(/\/resume\/999\/edit(?:\?.*)?$/, { timeout: 12_000 })
    await expect(page.getByPlaceholder('请输入目标公司名称')).toHaveValue('测试公司')
    await expect(page.getByPlaceholder('请输入目标岗位名称')).toHaveValue('前端工程师')
  })

  test('点击导出 PDF 后会真正触发下载并拿到 PDF 文件', async ({ page }, testInfo) => {
    await createResumeFromDashboard(page, uniqueEmail('pdfdownload'))

    await page.route('**/api/resumes/*/export', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          download_url: '/files/test-resume.pdf',
          filename: 'resume_test.pdf',
          format: 'pdf',
        }),
      })
    })
    await page.route('http://localhost:8000/files/test-resume.pdf', async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': 'attachment; filename="resume_test.pdf"',
        },
        body: '%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
      })
    })

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出 PDF' }).click()
    const download = await downloadPromise
    const savedPath = testInfo.outputPath('resume_test.pdf')
    await download.saveAs(savedPath)

    expect(download.suggestedFilename()).toBe('resume_test.pdf')
    const bytes = await fs.readFile(savedPath, 'utf8')
    expect(bytes.startsWith('%PDF-1.4')).toBeTruthy()
  })

  test('面试工作台只保留实时语音面试入口', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('interviewflow'))
    const baseResume = buildResumeResponse(Number(resumeId))

    const voiceSession = {
      id: 1,
      resume_id: Number(resumeId),
      target_title: '前端工程师',
      target_company: '测试公司',
      jd_text: '负责前端开发与性能优化',
      interview_type: 'general',
      difficulty: 'medium',
      language: 'zh-CN',
      mode: 'practice',
      status: 'interview_ready',
      current_round_index: 0,
      current_turn_index: 0,
      plan: null,
      turns: [],
      current_turn: null,
    }

    await page.route(`**/api/resumes/${resumeId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(baseResume),
      })
    })
    await page.route('**/api/interviews/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: voiceSession,
          next_action: 'voice',
        }),
      })
    })
    await page.route('**/api/interviews/1/end', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: { ...voiceSession, status: 'completed', ended_at: new Date().toISOString() },
          next_action: 'completed',
        }),
      })
    })
    await page.route('**/api/digital-human/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'volcengine',
          session_id: '1',
          status: 'ready',
        }),
      })
    })

    await page.goto(`/resume/${resumeId}/interview`)
    await expect(page.getByText('模拟面试 · 测试公司 · 前端工程师')).toBeVisible()
    await expect(page.getByRole('button', { name: /开始面试|继续面试|重试连接|挂断/ })).toBeVisible()
    await expect(page.getByPlaceholder('输入你的回答...')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '提交回答' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '给我提示' })).toHaveCount(0)
  })

  test('Resume Agent 可以展示流式 diff 并确认修改', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agentconfirm'))

    await installResumeAgentMock(page)
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText('我建议先强化项目结果表达。')).toBeVisible()
    await expect(page.getByText('工具运行中')).toBeVisible()
    await expect(page.locator('span').filter({ hasText: /^优化项目经历$/ }).first()).toBeVisible()
    await expect(page.getByText('主导前端重构，首屏加载提速 35%')).toBeVisible()
    await expect(page.getByText('TypeScript、FastAPI、Next.js')).toBeVisible()
    await expect(page.getByText('items: TypeScript、FastAPI、Next.js')).toHaveCount(0)
    await expect(page.getByText('skill_c10dbc140337')).toHaveCount(0)
    await expect(page.getByText('category: 编程语言')).toHaveCount(0)
    await expect(page.getByText('skill_same_json')).toHaveCount(0)
    await expect(page.getByText('精简技能列表，去掉与 Agent 开发核心不直接相关的条目')).toBeVisible()
    await expect(page.getByText('skill_truncated_json')).toHaveCount(0)
    await expect(page.getByText('精简：Few-shot Prompting 并入 Context Engineering')).toBeVisible()
    await expect(page.getByText('集成 Tavily Search API 实现实时联网搜索')).toBeVisible()
    await expect(page.getByText(/text:/)).toHaveCount(0)
    await expect(page.getByText('在提示词中引入 few-shot 策略')).toBeVisible()
    await expect(page.getByText('work_new_json')).toHaveCount(0)
    await expect(page.getByText('（新增）')).toHaveCount(0)
    await page.getByRole('button', { name: '确认修改' }).click()

    await expect(page.getByText('已应用修改。')).toBeVisible()
    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls).toHaveLength(1)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_e2e',
      call_id: 'call_e2e',
      confirmed: true,
    })
  })

  test('Resume Agent diff 不展示空值删除行', async ({ page }) => {
    const resume = buildResumeResponse(123)

    await installEditorApiMock(page, resume)
    await installResumeAgentMock(page, { includeEmptyBeforeDiff: true })
    await page.goto('/resume/123/edit')
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我更新求职目标')
    await input.press('Enter')

    await expect(page.locator('div.bg-green-50').filter({ hasText: /^\+\s*腾讯$/ })).toBeVisible()
    await expect(page.getByText('用户明确要求投递腾讯公司 Agent 开发岗')).toBeVisible()
    await expect(page.locator('div.bg-red-50').filter({ hasText: /^-\s*空$/ })).toHaveCount(0)
  })

  test('Resume Agent summary diff 不展示空值删除行', async ({ page }) => {
    const resume = buildResumeResponse(123)

    await installEditorApiMock(page, resume)
    await installResumeAgentMock(page, { includeEmptyBeforeDiff: true, omitDiffItems: true })
    await page.goto('/resume/123/edit')
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我更新求职目标')
    await input.press('Enter')

    await expect(page.locator('div.bg-green-50').filter({ hasText: /^\+\s*腾讯$/ })).toBeVisible()
    await expect(page.getByText('用户明确要求投递腾讯公司 Agent 开发岗')).toBeVisible()
    await expect(page.locator('div.bg-red-50').filter({ hasText: /^-\s*空$/ })).toHaveCount(0)
  })

  test('Resume Agent 流式 diff 变长时保持消息区贴底', async ({ page }) => {
    const resume = buildResumeResponse(123)
    const marker = '自动滚动验证项 39 改后'

    await installEditorApiMock(page, resume)
    await installResumeAgentMock(page, { extraDiffItemCount: 40 })
    await page.goto('/resume/123/edit')
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText(marker)).toBeAttached()
    await expect.poll(async () => {
      const metrics = await readNearestScrollMetrics(page, marker)
      return metrics?.distanceFromBottom ?? Number.POSITIVE_INFINITY
    }).toBeLessThanOrEqual(4)
  })

  test('Resume Agent 在工具事件阶段不额外显示思考中', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agenttoolstate'))

    await installResumeAgentMock(page, { pauseAfterToolCall: true })
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText('工具运行中')).toBeVisible()
    await expect(page.getByText('思考中')).toHaveCount(0)

    await page.evaluate(() => {
      const runtimeWindow = window as Window & {
        __resumeAgentContinueAfterToolCall?: () => void
      }
      runtimeWindow.__resumeAgentContinueAfterToolCall?.()
    })

    await expect(page.getByText('主导前端重构，首屏加载提速 35%')).toBeVisible()
    await expect(page.getByText('思考中')).toHaveCount(0)
  })

  test('Resume Agent 在待确认 diff 出现后仍保留工具运行状态', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agenttoolpending'))

    await installResumeAgentMock(page, { omitDiffItems: true })
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText('主导前端重构，首屏加载提速 35%')).toBeVisible()
    await expect(page.getByText('工具运行中')).toBeVisible()
    await expect(page.locator('span').filter({ hasText: /^优化项目经历$/ }).first()).toBeVisible()
  })

  test('Resume Agent 可以拒绝待确认的 diff 修改', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agentreject'))

    await installResumeAgentMock(page)
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.locator('span').filter({ hasText: /^优化项目经历$/ }).first()).toBeVisible()
    await page.getByRole('button', { name: '拒绝' }).click()

    await expect(page.getByText('已保留原文。')).toBeVisible()
    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls).toHaveLength(1)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_e2e',
      call_id: 'call_e2e',
      confirmed: false,
    })
  })

  test('Resume Agent 可以提交反馈重新生成待确认修改', async ({ page }) => {
    const resume = buildResumeResponse(126)

    await installEditorApiMock(page, resume)
    await installResumeAgentMock(page)
    await page.goto(`/resume/${resume.id}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByPlaceholder('输入你希望 Agent 重新生成时参考的反馈...')).toBeVisible()
    await page.getByPlaceholder('输入你希望 Agent 重新生成时参考的反馈...').fill('补充量化结果，不要只写高并发')
    await page.getByRole('button', { name: '重写修改' }).click()

    await expect(page.getByText('已按反馈重新生成修改。')).toBeVisible()
    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls).toHaveLength(1)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_e2e',
      call_id: 'call_e2e',
      confirmed: false,
      feedback: '补充量化结果，不要只写高并发',
    })
  })

  test('Resume Agent 待确认 diff 空闲后不会自动拒绝', async ({ page }) => {
    const resume = buildResumeResponse(124)

    await page.addInitScript(() => {
      const originalSetTimeout = window.setTimeout
      window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
        const normalizedTimeout = timeout === 5 * 60 * 1000 ? 1000 : timeout
        return originalSetTimeout(handler, normalizedTimeout, ...args)
      }) as typeof window.setTimeout
    })
    await installEditorApiMock(page, resume)
    await installResumeAgentMock(page)
    await page.goto(`/resume/${resume.id}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByPlaceholder('输入你希望 Agent 重新生成时参考的反馈...')).toBeVisible()
    await page.waitForTimeout(1200)

    await expect(page.getByPlaceholder('输入你希望 Agent 重新生成时参考的反馈...')).toBeVisible()
    await expect(page.getByRole('button', { name: '确认修改' })).toBeEnabled()
    await expect(page.getByRole('button', { name: '拒绝' })).toBeEnabled()
  })

  test('Resume Agent 可以在刷新后恢复待确认 diff', async ({ page }) => {
    const resume = buildResumeResponse(125)

    await installEditorApiMock(page, resume, [], {
      session_id: 'resume_session_restored',
      status: 'waiting_confirmation',
      pending_action: {
        type: 'tool_confirmation',
        call_id: 'call_restored',
        tool_name: '优化项目经历',
        tool_id: 'update_bullet',
        diff_summary: '改前 A 改后 B',
        diff_items: [
          {
            before: '旧要点',
            after: '新要点',
            reason: '更贴合 JD',
          },
        ],
      },
    })
    await installResumeAgentMock(page)
    await page.goto(`/resume/${resume.id}/edit`)
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('旧要点')).toBeVisible()
    await expect(page.getByText('新要点')).toBeVisible()
    await expect(page.getByPlaceholder('输入你希望 Agent 重新生成时参考的反馈...')).toBeVisible()
    await page.getByRole('button', { name: '拒绝' }).click()

    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_restored',
      call_id: 'call_restored',
      confirmed: false,
    })
  })
})
