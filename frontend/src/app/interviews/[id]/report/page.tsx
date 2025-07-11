'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import Link from 'next/link'
import { 
  ArrowLeftIcon,
  ChartBarIcon,
  ClockIcon,
  CalendarIcon,
  ShareIcon,
  DocumentArrowDownIcon,
  LinkIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'
import dynamic from 'next/dynamic'

// 动态导入图表组件以避免SSR问题
const RadarChartComponent = dynamic(
  () => import('@/components/charts/RadarChartComponent'),
  { 
    ssr: false,
    loading: () => (
      <div className="h-80 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }
)

interface InterviewReport {
  id: number
  resume_title: string
  job_position: string
  interview_mode: string
  jd_content: string
  overall_score: number
  performance_level: string
  interview_date: string
  duration_minutes: number
  total_questions: number
  competency_scores: {
    job_fit: number
    technical_depth: number
    project_exposition: number
    communication: number
    behavioral: number
  }
  ai_highlights: string[]
  ai_improvements: string[]
  conversation: {
    question: string
    answer: string
    ai_feedback: {
      score: number
      strengths: string[]
      suggestions: string[]
      reference_answer?: string
    }
  }[]
  jd_keywords: {
    keyword: string
    mentioned: boolean
    frequency: number
  }[]
  coverage_rate: number
  frequent_words: {
    word: string
    count: number
  }[]
}

export default function InterviewReportPage() {
  const params = useParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [report, setReport] = useState<InterviewReport | null>(null)
  const [reportLoading, setReportLoading] = useState(true)
  const [expandedFeedback, setExpandedFeedback] = useState<number[]>([])

  const reportId = params?.id as string

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 模拟数据加载（实际应该从API获取）
  useEffect(() => {
    if (mounted && isAuthenticated && reportId) {
      loadReportData()
    }
  }, [mounted, isAuthenticated, reportId])

  const loadReportData = async () => {
    setReportLoading(true)
    
    // 模拟API调用延迟
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 模拟报告数据
    const mockReport: InterviewReport = {
      id: parseInt(reportId),
      resume_title: "彭世雄简历2",
      job_position: "AI应用开发工程师",
      interview_mode: "综合面试",
      jd_content: "负责AI应用开发，熟悉RAG、LangChain等技术...",
      overall_score: 87,
      performance_level: "表现出色",
      interview_date: "2025年7月11日",
      duration_minutes: 25,
      total_questions: 5,
      competency_scores: {
        job_fit: 85,
        technical_depth: 92,
        project_exposition: 78,
        communication: 88,
        behavioral: 82
      },
      ai_highlights: [
        "您在阐述RAG项目时，清晰地展现了技术选型的深度思考，尤其是在处理PDF表格数据方面的解决方案，给面试官留下了深刻印象。",
        "对FastAPI和LangChain的理解深入，能够结合实际项目经验进行说明。"
      ],
      ai_improvements: [
        "在回答关于团队协作的行为问题时，可以更具体地引用一个实例，使用STAR法则来支撑您的论点，这会更有说服力。",
        "可以在技术回答中加入更多量化数据，如性能提升百分比、处理数据量等。"
      ],
      conversation: [
        {
          question: "请简单介绍一下您自己，包括您的技术背景和主要项目经验。",
          answer: "我是一名AI应用开发工程师，主要专注于RAG技术和大语言模型应用开发。我开发过一个基于LangChain的智能问答系统...",
          ai_feedback: {
            score: 8,
            strengths: ["清晰的自我定位", "突出了相关技术经验"],
            suggestions: ["可以加入具体的项目成果数据", "提及团队规模和个人贡献"]
          }
        },
        {
          question: "请详细描述一下您在RAG项目中遇到的技术挑战以及解决方案。",
          answer: "在RAG项目中，我遇到的主要挑战是处理PDF表格数据的结构化提取。我使用了pdfplumber结合正则表达式的方法...",
          ai_feedback: {
            score: 9,
            strengths: ["技术细节描述清晰", "解决方案具体可行", "体现了问题解决能力"],
            suggestions: ["可以提及性能改进的具体数据", "说明方案的可扩展性"]
          }
        }
      ],
      jd_keywords: [
        { keyword: "RAG", mentioned: true, frequency: 3 },
        { keyword: "LangChain", mentioned: true, frequency: 2 },
        { keyword: "FastAPI", mentioned: false, frequency: 0 },
        { keyword: "Python", mentioned: true, frequency: 1 },
        { keyword: "团队协作", mentioned: true, frequency: 1 }
      ],
      coverage_rate: 75,
      frequent_words: [
        { word: "项目", count: 5 },
        { word: "技术", count: 4 },
        { word: "开发", count: 3 },
        { word: "数据", count: 3 }
      ]
    }
    
    setReport(mockReport)
    setReportLoading(false)
  }

  const toggleFeedback = (index: number) => {
    setExpandedFeedback(prev => 
      prev.includes(index) 
        ? prev.filter(i => i !== index)
        : [...prev, index]
    )
  }

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600'
    if (score >= 80) return 'text-blue-600'
    if (score >= 70) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getScoreLevel = (score: number) => {
    if (score >= 90) return '优秀'
    if (score >= 80) return '良好' 
    if (score >= 70) return '中等'
    return '需改进'
  }

  // 能力雷达图数据
  const radarData = report ? [
    { subject: '岗位匹配度', A: report.competency_scores.job_fit, fullMark: 100 },
    { subject: '技术深度', A: report.competency_scores.technical_depth, fullMark: 100 },
    { subject: '项目阐述', A: report.competency_scores.project_exposition, fullMark: 100 },
    { subject: '沟通表达', A: report.competency_scores.communication, fullMark: 100 },
    { subject: '行为表现', A: report.competency_scores.behavioral, fullMark: 100 }
  ] : []

  if (!mounted || isLoading || reportLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在生成面试报告...</p>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">报告不存在</p>
          <Link href="/interviews" className="btn-primary mt-4">
            返回面试中心
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <Link
              href="/interviews"
              className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5" />
              <span>返回面试中心</span>
            </Link>
            
            {/* 操作按钮 */}
            <div className="flex items-center space-x-3">
              <button className="btn-secondary flex items-center space-x-2 text-sm">
                <LinkIcon className="w-4 h-4" />
                <span>复制链接</span>
              </button>
              <button className="btn-secondary flex items-center space-x-2 text-sm">
                <DocumentArrowDownIcon className="w-4 h-4" />
                <span>下载PDF</span>
              </button>
              <button className="btn-primary flex items-center space-x-2 text-sm">
                <ArrowPathIcon className="w-4 h-4" />
                <span>再来一次</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          {/* 模块一：顶部摘要与总体评估 */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">
              {report.job_position} - 模拟面试分析报告
            </h1>
            
            {/* 核心数据卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="col-span-1 md:col-span-1 card p-6 text-center">
                <div className={`text-5xl font-bold mb-2 ${getScoreColor(report.overall_score)}`}>
                  {report.overall_score}
                </div>
                <div className="text-lg font-medium text-gray-900 mb-1">
                  {getScoreLevel(report.overall_score)}
                </div>
                <div className="text-sm text-gray-500">综合得分</div>
              </div>
              
              <div className="col-span-1 md:col-span-3 card p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-gray-500 mb-1">基于简历</div>
                    <div className="font-medium">{report.resume_title}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 mb-1">面试时间</div>
                    <div className="font-medium">{report.interview_date}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 mb-1">总用时</div>
                    <div className="font-medium">{report.duration_minutes} 分钟 • {report.total_questions} 题</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 能力雷达图和AI评语 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 能力雷达图 */}
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">能力评估</h3>
                <RadarChartComponent data={radarData} />
              </div>

              {/* AI总体评语 */}
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">AI 总体评语</h3>
                
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-green-700 mb-2 flex items-center">
                      ✨ 亮点表现
                    </h4>
                    <div className="space-y-2">
                      {report.ai_highlights.map((highlight, index) => (
                        <p key={index} className="text-sm text-gray-700 bg-green-50 p-3 rounded-lg">
                          {highlight}
                        </p>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-blue-700 mb-2 flex items-center">
                      💡 改进建议
                    </h4>
                    <div className="space-y-2">
                      {report.ai_improvements.map((improvement, index) => (
                        <p key={index} className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg">
                          {improvement}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 模块二：完整对话与逐题分析 */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">逐题详细分析</h2>
            
            <div className="space-y-6">
              {report.conversation.map((item, index) => (
                <div key={index} className="card p-6">
                  {/* 面试官问题 */}
                  <div className="flex justify-start mb-4">
                    <div className="max-w-[85%]">
                      <div className="flex items-center mb-2">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3">
                          <span className="text-sm font-medium text-blue-600">面</span>
                        </div>
                        <span className="text-sm text-gray-500">面试官</span>
                      </div>
                      <div className="bg-blue-50 text-blue-900 px-4 py-3 rounded-lg rounded-tl-sm border border-blue-200">
                        {item.question}
                      </div>
                    </div>
                  </div>

                  {/* 你的回答 */}
                  <div className="flex justify-end mb-4">
                    <div className="max-w-[85%]">
                      <div className="flex items-center justify-end mb-2">
                        <span className="text-sm text-gray-500 mr-3">你的回答</span>
                        <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                          <span className="text-sm font-medium text-gray-600">你</span>
                        </div>
                      </div>
                      <div className="bg-gray-100 text-gray-900 px-4 py-3 rounded-lg rounded-tr-sm border border-gray-200">
                        {item.answer}
                      </div>
                    </div>
                  </div>

                  {/* AI反馈卡片 */}
                  <div className="mt-4">
                    <button
                      onClick={() => toggleFeedback(index)}
                      className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
                    >
                      <ChartBarIcon className="w-4 h-4" />
                      <span>
                        {expandedFeedback.includes(index) ? '收起AI反馈' : '展开AI反馈'}
                      </span>
                      <span className="font-medium">({item.ai_feedback.score}/10)</span>
                    </button>
                    
                    {expandedFeedback.includes(index) && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-4"
                      >
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <h5 className="text-sm font-medium text-green-700 mb-2">✅ 优点分析</h5>
                            <ul className="space-y-1">
                              {item.ai_feedback.strengths.map((strength, i) => (
                                <li key={i} className="text-sm text-gray-700">• {strength}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h5 className="text-sm font-medium text-blue-700 mb-2">💡 优化建议</h5>
                            <ul className="space-y-1">
                              {item.ai_feedback.suggestions.map((suggestion, i) => (
                                <li key={i} className="text-sm text-gray-700">• {suggestion}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 模块三：关键词与技能分析 */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">技能与关键词分析</h2>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* JD关键词覆盖率 */}
              <div className="card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">JD关键词覆盖率</h3>
                  <span className="text-2xl font-bold text-blue-600">{report.coverage_rate}%</span>
                </div>
                
                <div className="space-y-2">
                  {report.jd_keywords.map((keyword, index) => (
                    <div 
                      key={index}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg ${
                        keyword.mentioned 
                          ? 'bg-green-50 border border-green-200' 
                          : 'bg-gray-50 border border-gray-200'
                      }`}
                    >
                      <span className={`font-medium ${
                        keyword.mentioned ? 'text-green-800' : 'text-gray-500'
                      }`}>
                        {keyword.keyword}
                      </span>
                      <div className="flex items-center space-x-2">
                        {keyword.mentioned && (
                          <span className="text-xs text-green-600">
                            {keyword.frequency}次
                          </span>
                        )}
                        <span className={`text-xs ${
                          keyword.mentioned ? 'text-green-600' : 'text-gray-400'
                        }`}>
                          {keyword.mentioned ? '✓' : '✗'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 高频词分析 */}
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">高频词分析</h3>
                
                <div className="space-y-3">
                  {report.frequent_words.map((word, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">{word.word}</span>
                      <div className="flex items-center space-x-3">
                        <div className="w-24 bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${(word.count / report.frequent_words[0].count) * 100}%` }}
                          ></div>
                        </div>
                        <span className="text-sm text-gray-500 w-8 text-right">{word.count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  )
}