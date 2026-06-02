// 用于提供 resume-template-style.spec.ts 端到端测试逻辑。
import { expect, test } from '@playwright/test'

// 用于处理encodeprintpayload。
function encodePrintPayload(payload: Record<string, unknown>) {
  return Buffer.from(JSON.stringify(payload)).toString('base64url')
}

// 用于统计 Playwright 生成的 PDF 页数。
function countPdfPages(pdf: Buffer) {
  const text = pdf.toString('latin1')
  return (text.match(/\/Type\s*\/Page\b/g) || []).length
}

test.describe('简历模板样式', () => {
  test('打印页不触发登录态刷新', async ({ page }) => {
    const authRequests: string[] = []
    const payload = encodePrintPayload({
      template: 'classic',
      content: {
        personal_info: {
          name: '打印页',
          email: 'print@example.com',
        },
        education: [],
        skills: [],
        work_experience: [],
        projects: [],
      },
    })

    await page.route('**/api/auth/**', async (route) => {
      authRequests.push(route.request().url())
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid refresh token' }),
      })
    })

    await page.goto(`/resume/print?data=${payload}`)
    await expect(page.getByRole('heading', { name: '打印页' })).toBeVisible()

    expect(authRequests).toEqual([])
  })

  test('绿色页眉模板按截图风格渲染页眉和分隔标题', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'emerald',
      content: {
        personal_info: {
          name: '彭世雄',
          position: 'AI Agent开发工程师',
          phone: '18980162782',
          email: 'psx849261680@gmail.com',
          github: 'https://github.com/849261680',
          website: 'https://psx1.vercel.app',
        },
        education: [
          {
            school: '东北大学',
            degree: '本科',
            major: '信息安全',
            duration: '2019–2023',
          },
        ],
        skills: [
          {
            category: '编程语言',
            items: ['Python'],
          },
        ],
        work_experience: [
          {
            company: '世优科技',
            position: 'AI Agent开发工程师',
            duration: '2025/08 - 2025/11',
            highlights: [{ text: '参与设计并实现了 MoYi AI 的核心架构' }],
          },
        ],
        projects: [
          {
            name: 'Chat Resume',
            role: '核心开发者',
            duration: '2025/06 - 2025/07',
            overview: 'AI 驱动的求职辅导平台',
            highlights: [{ text: '实现简历优化链路' }],
          },
        ],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)

    const pageSheet = page.locator('.resume-page.resume-template-emerald:not(.invisible)').first()
    await expect(pageSheet).toBeVisible()

    const header = pageSheet.locator('.resume-emerald-personal')
    await expect(header).toBeVisible()
    await expect(header).toHaveCSS('background-color', 'rgb(5, 150, 105)')
    await expect(header).toContainText('psx849261680@gmail.com')
    await expect(header).toContainText('https://github.com/849261680')
    await expect(header).toContainText('https://psx1.vercel.app')
    await expect(header.locator('a[href="https://github.com/849261680"]')).toHaveText('https://github.com/849261680')
    await expect(header.locator('a[href="https://psx1.vercel.app"]')).toHaveText('https://psx1.vercel.app')

    await expect.poll(async () => {
      const pageBox = await pageSheet.evaluate((element) => element.getBoundingClientRect().toJSON())
      const headerBox = await header.evaluate((element) => element.getBoundingClientRect().toJSON())
      return Math.round(pageBox.width - headerBox.width)
    }).toBeLessThanOrEqual(4)

    const nameBox = await header.getByRole('heading', { name: '彭世雄' }).evaluate((element) => element.getBoundingClientRect().toJSON())
    const pageBox = await pageSheet.evaluate((element) => element.getBoundingClientRect().toJSON())
    expect(Math.round(nameBox.y - pageBox.y)).toBeGreaterThanOrEqual(20)

    const educationHeading = pageSheet.getByRole('heading', { name: '教育经历' })
    await expect(educationHeading).toHaveCSS('text-align', 'center')
    await expect(educationHeading).toHaveCSS('border-bottom-width', '0px')

    const workItem = pageSheet.locator('.resume-emerald-item').filter({ hasText: '世优科技' }).first()
    const projectItem = pageSheet.locator('.resume-emerald-item').filter({ hasText: 'Chat Resume' }).first()
    const companyText = workItem.getByText('世优科技', { exact: true })
    const workDateText = workItem.getByText('2025/08 - 2025/11', { exact: true })
    const projectNameText = projectItem.getByText('Chat Resume', { exact: true })
    const projectDateText = projectItem.getByText('2025/06 - 2025/07', { exact: true })
    await expect(companyText).toBeVisible()
    await expect(workDateText).toBeVisible()
    await expect(projectNameText).toBeVisible()
    await expect(projectDateText).toBeVisible()
    await expect.poll(async () => {
      const companyBox = await companyText.evaluate((element) => element.getBoundingClientRect().toJSON())
      const workDateBox = await workDateText.evaluate((element) => element.getBoundingClientRect().toJSON())
      const projectNameBox = await projectNameText.evaluate((element) => element.getBoundingClientRect().toJSON())
      const projectDateBox = await projectDateText.evaluate((element) => element.getBoundingClientRect().toJSON())
      return {
        workDateRightAligned: workDateBox.x > companyBox.x,
        projectDateRightAligned: projectDateBox.x > projectNameBox.x,
        workDateSameLine: Math.abs(workDateBox.y - companyBox.y) < 6,
        projectDateSameLine: Math.abs(projectDateBox.y - projectNameBox.y) < 6,
      }
    }).toEqual({
      workDateRightAligned: true,
      projectDateRightAligned: true,
      workDateSameLine: true,
      projectDateSameLine: true,
    })
  })

  test('正式黑白模板按截图风格渲染联系信息和页面样式', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'formal',
      content: {
        personal_info: {
          name: '彭世雄',
          position: 'AI Agent开发工程师',
          phone: '18980162782',
          email: 'psx849261680@gmail.com',
          github: 'https://github.com/849261680',
          website: 'https://psx1.vercel.app',
        },
        education: [
          {
            school: '东北大学',
            degree: '本科',
            major: '信息安全',
            duration: '2019–2023',
          },
        ],
        skills: [
          {
            category: '编程语言',
            items: ['Python'],
          },
        ],
        work_experience: [],
        projects: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)

    const pageSheet = page.locator('.resume-page.resume-template-formal:not(.invisible)').first()
    await expect(pageSheet).toBeVisible()
    await expect(page.getByRole('heading', { name: '彭世雄' })).toHaveCSS('text-align', 'left')
    await expect(pageSheet).toContainText('GitHub: https://github.com/849261680')
    await expect(pageSheet).toContainText('个人网站: https://psx1.vercel.app')
    await expect(pageSheet.locator('a[href="https://github.com/849261680"]')).toHaveText('https://github.com/849261680')
    await expect(pageSheet.locator('a[href="https://psx1.vercel.app"]')).toHaveText('https://psx1.vercel.app')
  })

  test('打印页复用导出载荷中的布局配置', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'classic',
      layout_config: {
        density: 'compact',
        moduleOrder: ['personal', 'work', 'projects', 'skills', 'education'],
        visibleModules: ['personal', 'work'],
        spacingScale: 0.7,
        templateStyle: 'classic',
      },
      content: {
        personal_info: {
          name: '布局导出',
          email: 'layout@example.com',
        },
        education: [
          {
            school: '不应显示大学',
            degree: '本科',
            major: '计算机',
            duration: '2019-2023',
          },
        ],
        work_experience: [
          {
            company: '优先工作经历',
            position: '工程师',
            duration: '2024-至今',
          },
        ],
        skills: [
          {
            category: '不应显示技能',
            items: ['TypeScript'],
          },
        ],
        projects: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)

    const pageSheet = page.locator('.resume-page.resume-template-classic:not(.invisible)').first()
    await expect(pageSheet).toBeVisible()
    await expect(pageSheet).toContainText('布局导出')
    await expect(pageSheet).toContainText('优先工作经历')
    await expect(pageSheet).not.toContainText('不应显示大学')
    await expect(pageSheet).not.toContainText('不应显示技能')
  })

  test('单页打印页不会产生尾部空白页', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'classic',
      content: {
        personal_info: {
          name: '单页打印',
          email: 'one-page@example.com',
        },
        education: [
          {
            school: '测试大学',
            degree: '本科',
            major: '计算机',
            duration: '2019-2023',
          },
        ],
        work_experience: [
          {
            company: '测试公司',
            position: '工程师',
            duration: '2024-至今',
            highlights: [{ text: '负责简历打印页一致性修复。' }],
          },
        ],
        skills: [],
        projects: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    await page.locator('.resume-page').first().waitFor({ state: 'attached' })
    await page.emulateMedia({ media: 'print' })
    await page.waitForFunction(() => {
      return Array.from(document.querySelectorAll('.resume-page')).some((element) => {
        const style = window.getComputedStyle(element)
        return style.display !== 'none' && style.visibility !== 'hidden'
      })
    })

    const printState = await page.evaluate(() => {
      return Array.from(document.querySelectorAll<HTMLElement>('.resume-page')).map((element) => {
        const style = window.getComputedStyle(element)
        const rect = element.getBoundingClientRect()
        return {
          display: style.display,
          pageBreakAfter: style.pageBreakAfter,
          breakAfter: style.breakAfter,
          height: rect.height,
          width: rect.width,
          visible: style.display !== 'none' && style.visibility !== 'hidden',
        }
      })
    })

    const printablePages = printState.filter((item) => item.visible)
    expect(printablePages).toHaveLength(1)
    expect(printablePages[0].width).toBeGreaterThan(793)
    expect(printablePages[0].height).toBeGreaterThan(1120)
    expect(printablePages[0].pageBreakAfter).not.toBe('always')
    expect(printablePages[0].breakAfter).not.toBe('page')
  })

  test('打印页切换 print media 后仍会重新标记分页就绪', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'classic',
      layout_config: {
        density: 'custom',
        moduleOrder: ['personal', 'summary', 'education', 'work', 'projects', 'skills'],
        visibleModules: ['personal', 'education', 'work', 'projects', 'skills'],
        spacingScale: 2,
        templateStyle: 'classic',
      },
      content: {
        personal_info: {
          name: '导出验证',
          email: 'export@test.example',
          phone: '13800000000',
        },
        summary: { text: '用于验证切换 print media 后不会截到分页计算状态。' },
        education: [
          {
            school: '测试大学',
            degree: '本科',
            major: '计算机',
            duration: '2019-2023',
          },
        ],
        work_experience: [
          {
            company: '测试公司',
            position: '工程师',
            duration: '2024-至今',
            highlights: [{ text: '负责导出链路稳定性修复。' }],
          },
        ],
        projects: [
          {
            name: 'Chat Resume',
            overview: 'AI 求职辅导平台。',
            highlights: [{ text: '修复打印页导出等待分页稳定。' }],
          },
        ],
        skills: [{ category: '技术栈', items: ['Next.js', 'FastAPI'] }],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    await page.waitForSelector('[data-resume-print-ready="true"]', { state: 'attached' })
    await page.waitForSelector('#resume-export-content .resume-page')
    await page.emulateMedia({ media: 'print' })
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))

    await page.waitForSelector('[data-resume-print-ready="true"]', { state: 'attached' })
    await expect(page.getByText('正在计算分页')).toHaveCount(0)
    await expect(page.locator('#resume-export-content .resume-page')).toHaveCount(1)
  })

  test('打印页忽略缺少文本的教育要点并完成导出就绪', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'emerald',
      layout_config: {
        moduleOrder: ['personal', 'education', 'work'],
        visibleModules: ['personal', 'education', 'work'],
        spacingScale: 0.55,
        templateStyle: 'emerald',
      },
      content: {
        personal_info: {
          name: '导出异常样本',
          email: 'export@test.example',
        },
        education: [
          {
            school: '东北大学（985）',
            degree: '本科',
            major: '信息安全',
            highlights: [{ id: 'hl_missing_text' }],
          },
        ],
        work_experience: [
          {
            company: '测试公司',
            position: 'AI Agent开发工程师',
            highlights: [{ text: '负责 Agent 导出链路稳定性。' }],
          },
        ],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    await page.waitForSelector('[data-resume-print-ready="true"]', {
      state: 'attached',
      timeout: 5_000,
    })
    await expect(page.locator('#resume-export-content .resume-page')).toHaveCount(1)
    await expect(page.locator('#resume-export-content li')).toHaveCount(1)
  })

  test('单页打印页导出的 PDF 只有一页', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'emerald',
      content: {
        personal_info: {
          name: '彭世雄',
          position: 'AI Agent开发工程师',
          phone: '18980162782',
          email: 'psx849261680@gmail.com',
          github: 'https://github.com/849261680',
        },
        education: [
          {
            school: '东北大学',
            degree: '本科',
            major: '信息安全',
            duration: '2019-2023',
          },
        ],
        work_experience: [
          {
            company: '世优科技',
            position: 'AI Agent开发工程师',
            duration: '2025/08 - 2025/11',
            highlights: [
              { text: '设计 Agent Planning、Tool Use、Memory 多阶段执行链路。' },
              { text: '基于 RAG 检索增强构建企业知识库问答与任务执行。' },
            ],
          },
        ],
        projects: [
          {
            name: 'Chat Resume',
            role: '核心开发者',
            duration: '2025',
            overview: 'AI 驱动的求职辅导平台。',
            highlights: [
              { text: '集成 MCP 工具调用、简历解析和模拟面试工作流。' },
              { text: '实现 JD 匹配度分析和结构化优化建议。' },
            ],
          },
        ],
        skills: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    await expect(page.locator('.resume-page.resume-template-emerald:not(.invisible)').first()).toBeVisible()

    const pdf = await page.pdf({
      format: 'A4',
      margin: { top: '0', right: '0', bottom: '0', left: '0' },
      preferCSSPageSize: true,
      printBackground: true,
    })

    expect(countPdfPages(pdf)).toBe(1)
  })

  test('分页断点落在文字行上，避免页尾大块空白', async ({ page }) => {
    const longText = '针对复杂项目经历描述较长时的换行场景，分页器应该继续把下一条可见文字行排到当前页底部，而不是把整个项目块推到下一页造成大块空白。'
    const payload = encodePrintPayload({
      template: 'formal',
      content: {
        personal_info: {
          name: '分页测试',
          email: 'page-break@example.com',
        },
        education: [],
        skills: [],
        work_experience: [],
        projects: Array.from({ length: 7 }, (_, index) => ({
          name: `分页项目 ${index + 1}`,
          role: '核心开发者',
          duration: `2025.0${index + 1}-2025.0${index + 2}`,
          demo_url: 'https://example.com/demo',
          github_url: 'https://github.com/example/resume-pagination',
          overview: longText,
          highlights: [
            { text: `${longText} 第一条成果覆盖搜索、匹配和建议闭环。` },
            { text: `${longText} 第二条成果覆盖多轮对话和结构化输出。` },
            { text: `${longText} 第三条成果覆盖成本控制和稳定性。` },
            { text: `${longText} 第四条成果覆盖实时反馈和报告生成。` },
          ],
        })),
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    await expect.poll(async () => page.locator('.resume-page').count()).toBeGreaterThan(1)

    const firstPageBottomGap = await page.locator('.resume-page').first().evaluate((pageElement) => {
      const pageBox = pageElement.getBoundingClientRect()
      const styles = window.getComputedStyle(pageElement)
      const scaleY = pageBox.height / (pageElement as HTMLElement).offsetHeight
      const contentTop = pageBox.top + (parseFloat(styles.paddingTop) || 0) * scaleY
      const contentBottom = pageBox.bottom - (parseFloat(styles.paddingBottom) || 0) * scaleY
      const walker = document.createTreeWalker(pageElement, NodeFilter.SHOW_TEXT)
      const range = document.createRange()
      let maxBottom = contentTop
      let node = walker.nextNode()

      while (node) {
        if (node.textContent?.trim()) {
          range.selectNodeContents(node)
          Array.from(range.getClientRects()).forEach((rect) => {
            const intersectsPage = rect.bottom > contentTop && rect.top < contentBottom
            if (intersectsPage) {
              maxBottom = Math.max(maxBottom, Math.min(rect.bottom, contentBottom))
            }
          })
        }
        node = walker.nextNode()
      }

      range.detach()
      return (contentBottom - maxBottom) / scaleY
    })

    expect(firstPageBottomGap).toBeLessThan(90)
  })

  test('分页页尾不会露出下一页的长 bullet 尾行', async ({ page }) => {
    const targetText = '实现 SSE 流式推送研究进度（planning → search_result → step_complete → deep_research_decision → report_complete），并建设 CostTracker 与 ResearchMetrics 记录 token、搜索次数、来源数量与耗时，使长任务研究过程可观测'
    const fillerText = '负责 Agent 工具链建设，覆盖规划、调用、确认、回滚和结果同步。'
    const payload = encodePrintPayload({
      template: 'formal',
      content: {
        personal_info: {
          name: '分页复现',
          email: 'page@example.com',
        },
        education: [],
        skills: [],
        work_experience: [],
        projects: [
          {
            name: 'Deep Research Agent',
            role: '全栈工程师',
            duration: '2026',
            overview: '研究型 Agent 平台。',
            highlights: [
              ...Array.from({ length: 29 }, (_, index) => ({
                text: `${fillerText} ${index}`,
              })),
              { text: targetText },
            ],
          },
        ],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)
    const visiblePages = page.locator('.resume-page:not(.invisible)')
    await expect.poll(async () => visiblePages.count()).toBeGreaterThan(1)

    const leakedTargetLineCount = await visiblePages.first().evaluate((pageElement, target) => {
      const pageBox = pageElement.getBoundingClientRect()
      const styles = window.getComputedStyle(pageElement)
      const scaleY = pageBox.height / (pageElement as HTMLElement).offsetHeight
      const contentTop = pageBox.top + (parseFloat(styles.paddingTop) || 0) * scaleY
      const contentBottom = pageBox.bottom - (parseFloat(styles.paddingBottom) || 0) * scaleY
      const walker = document.createTreeWalker(pageElement, NodeFilter.SHOW_TEXT)
      const range = document.createRange()
      let leakedLines = 0
      let node = walker.nextNode()

      while (node) {
        if (!node.textContent?.includes(target)) {
          node = walker.nextNode()
          continue
        }

        range.selectNodeContents(node)
        for (const rect of Array.from(range.getClientRects())) {
          if (rect.bottom <= contentTop || rect.top >= contentBottom) continue

          const visibleTop = Math.max(rect.top, contentTop)
          const visibleBottom = Math.min(rect.bottom, contentBottom)
          const probeElement = document.elementFromPoint(rect.left + 8, (visibleTop + visibleBottom) / 2)
          if (probeElement?.textContent?.includes(target)) {
            leakedLines += 1
          }
        }
        node = walker.nextNode()
      }

      range.detach()
      return leakedLines
    }, targetText)

    expect(leakedTargetLineCount).toBe(0)
  })

  test('所有简历模板头像使用更小尺寸', async ({ page }) => {
    const photoUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='
    for (const template of ['classic', 'formal', 'emerald']) {
      const payload = encodePrintPayload({
        template,
        content: {
          personal_info: {
            name: '头像尺寸',
            email: 'photo@example.com',
            photo_url: photoUrl,
          },
          education: [],
          skills: [],
          work_experience: [],
          projects: [],
        },
      })

      await page.goto(`/resume/print?data=${payload}`)
      const avatar = page.locator('#resume-export-content .resume-page img[alt="头像尺寸"]')
      await expect(avatar).toBeVisible()
      const avatarSize = await avatar.evaluate((image) => ({
        width: (image as HTMLImageElement).offsetWidth,
        height: (image as HTMLImageElement).offsetHeight,
      }))

      expect(avatarSize).toEqual({ width: 72, height: 88 })
    }
  })

  test('Emerald 正文行高随 spacingScale 压缩：低密度下长 bullet 高度减少', async ({ page }) => {
    const longBullet = '负责设计并实现 MoYi AI 的核心 Agent 执行链路，覆盖任务规划、工具调用、记忆管理与多轮对话，'
      + '并基于 RAG 检索增强构建企业知识库问答，结合成本追踪与可观测指标，使长任务研究过程稳定可控且持续可优化。'

    const buildPayload = (spacingScale: number) => encodePrintPayload({
      template: 'emerald',
      layout_config: {
        moduleOrder: ['personal', 'work'],
        visibleModules: ['personal', 'work'],
        spacingScale,
        templateStyle: 'emerald',
      },
      content: {
        personal_info: { name: '行高样本', email: 'line-height@example.com' },
        education: [],
        skills: [],
        projects: [],
        work_experience: [
          {
            company: '世优科技',
            position: 'AI Agent开发工程师',
            duration: '2025',
            highlights: [{ text: longBullet }],
          },
        ],
      },
    })

    // 渲染指定 spacingScale，返回长 bullet 的渲染高度（已换行成多行）。
    const measureBulletHeight = async (spacingScale: number) => {
      await page.goto(`/resume/print?data=${buildPayload(spacingScale)}`)
      const bullet = page.locator('.resume-page.resume-template-emerald:not(.invisible) .resume-emerald-list li').first()
      await expect(bullet).toBeVisible()
      return bullet.evaluate((element) => element.getBoundingClientRect().height)
    }

    const looseHeight = await measureBulletHeight(1)
    const tightHeight = await measureBulletHeight(0.5)

    // 长 bullet 必须换行才能体现行高差异
    expect(looseHeight).toBeGreaterThan(40)
    // 低 spacingScale 下行距压缩，整体高度应明显减少
    expect(tightHeight).toBeLessThan(looseHeight)
  })
})
