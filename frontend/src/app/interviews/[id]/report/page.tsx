'use client'

import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { interviewApi } from '@/lib/api'
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
import MarkdownMessage from '@/components/ui/MarkdownMessage'

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
  answered_questions: number
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
  all_questions?: {
    question: string
    type?: string
    index: number
  }[]
  reference_answers?: {
    question: string
    reference_answer: string
    index: number
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
  const searchParams = useSearchParams()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [report, setReport] = useState<InterviewReport | null>(null)
  const [reportLoading, setReportLoading] = useState(true)
  const [expandedFeedback, setExpandedFeedback] = useState<number[]>([])

  const reportId = params?.id as string
  const resumeId = searchParams?.get('resume_id')

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 从API获取报告数据
  useEffect(() => {
    if (mounted && isAuthenticated && reportId && resumeId) {
      loadReportData()
    }
  }, [mounted, isAuthenticated, reportId, resumeId])

  const loadReportData = async (regenerate: boolean = false) => {
    if (!resumeId) {
      console.error('Resume ID is missing from URL parameters')
      setReportLoading(false)
      return
    }
    
    setReportLoading(true)
    
    try {
      const sessionId = parseInt(reportId)
      const resumeIdNum = parseInt(resumeId)
      
      console.log(`正在获取面试报告: resumeId=${resumeIdNum}, sessionId=${sessionId}, regenerate=${regenerate}`)
      
      const reportData = await interviewApi.getInterviewReport(resumeIdNum, sessionId, regenerate)
      console.log('获取到的报告数据:', reportData)
      
      setReport(reportData)
      
    } catch (error) {
      console.error('Failed to load report data:', error)
      
      // 如果API调用失败，显示错误或使用默认数据
      const errorReport: InterviewReport = {
        id: parseInt(reportId),
        resume_title: "面试报告",
        job_position: "无法加载职位信息",
        interview_mode: "unknown",
        jd_content: "",
        overall_score: 0,
        performance_level: "无法生成报告",
        interview_date: "未知时间",
        duration_minutes: 0,
        total_questions: 0,
        competency_scores: {
          job_fit: 0,
          technical_depth: 0,
          project_exposition: 0,
          communication: 0,
          behavioral: 0
        },
        ai_highlights: ["报告生成失败，请稍后重试"],
        ai_improvements: ["无法获取改进建议"],
        conversation: [],
        jd_keywords: [],
        coverage_rate: 0,
        frequent_words: []
      }
      
      setReport(errorReport)
    } finally {
      setReportLoading(false)
    }
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
          <p className="text-gray-600">
            {reportLoading ? '正在生成面试报告...' : '正在加载...'}
          </p>
          {reportLoading && (
            <p className="text-sm text-gray-500 mt-2">
              AI正在分析您的面试表现，请稍候
            </p>
          )}
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
              <button 
                onClick={() => loadReportData(true)}
                disabled={reportLoading}
                className="btn-primary flex items-center space-x-2 text-sm disabled:opacity-50"
              >
                <ArrowPathIcon className={`w-4 h-4 ${reportLoading ? 'animate-spin' : ''}`} />
                <span>{reportLoading ? '生成中...' : '重新生成'}</span>
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
                    <div className="font-medium">{report.duration_minutes} 分钟 • {report.answered_questions}/{report.total_questions} 题</div>
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
                      亮点表现
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
                      改进建议
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
              {/* 显示所有问题，包括已回答和未回答的 */}
              {(report.all_questions || []).map((questionItem, questionIndex) => {
                // 找到对应的回答和反馈
                const conversation = report.conversation.find(conv => conv.question === questionItem.question)
                const isAnswered = !!conversation
                
                // 找到对应的AI参考答案
                const referenceAnswer = report.reference_answers?.find(ref => ref.question === questionItem.question)
                
                return (
                  <div key={questionIndex} className="card p-6">
                    {/* 问题标题 */}
                    <div className="flex items-center mb-4">
                      <span className="text-sm font-medium text-gray-500 mr-2">问题 {questionIndex + 1}</span>
                      {isAnswered ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">已回答</span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">未回答</span>
                      )}
                    </div>
                    
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
                          {questionItem.question}
                        </div>
                      </div>
                    </div>

                    {/* 你的回答（如果已回答） */}
                    {isAnswered && (
                      <div className="flex justify-end mb-4">
                        <div className="max-w-[85%]">
                          <div className="flex items-center justify-end mb-2">
                            <span className="text-sm text-gray-500 mr-3">你的回答</span>
                            <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                              <span className="text-sm font-medium text-gray-600">你</span>
                            </div>
                          </div>
                          <div className="bg-gray-100 text-gray-900 px-4 py-3 rounded-lg rounded-tr-sm border border-gray-200">
                            {conversation.answer}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* AI参考答案 */}
                    {referenceAnswer && (
                      <div className="flex justify-start mb-4">
                        <div className="max-w-[85%]">
                          <div className="flex items-center mb-2">
                            <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center mr-3">
                              <span className="text-sm font-medium text-purple-600">AI</span>
                            </div>
                            <span className="text-sm text-gray-500">AI参考答案</span>
                          </div>
                          <div className="bg-purple-50 text-purple-900 px-4 py-3 rounded-lg rounded-tl-sm border border-purple-200">
                            <MarkdownMessage content={referenceAnswer.reference_answer} />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* AI反馈卡片（仅对已回答的问题显示） */}
                    {isAnswered && (
                      <div className="mt-4">
                        <button
                          onClick={() => toggleFeedback(questionIndex)}
                          className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
                        >
                          <ChartBarIcon className="w-4 h-4" />
                          <span>
                            {expandedFeedback.includes(questionIndex) ? '收起AI反馈' : '展开AI反馈'}
                          </span>
                          <span className="font-medium">({conversation.ai_feedback.score}/10)</span>
                        </button>
                        
                        {expandedFeedback.includes(questionIndex) && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-4"
                          >
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <h5 className="text-sm font-medium text-green-700 mb-2">优点分析</h5>
                                <ul className="space-y-1">
                                  {conversation.ai_feedback.strengths.map((strength, i) => (
                                    <li key={i} className="text-sm text-gray-700">• {strength}</li>
                                  ))}
                                </ul>
                              </div>
                              <div>
                                <h5 className="text-sm font-medium text-blue-700 mb-2">优化建议</h5>
                                <ul className="space-y-1">
                                  {conversation.ai_feedback.suggestions.map((suggestion, i) => (
                                    <li key={i} className="text-sm text-gray-700">• {suggestion}</li>
                                  ))}
                                </ul>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
              
              {/* 如果没有all_questions数据，回退到原来的显示方式 */}
              {(!report.all_questions || report.all_questions.length === 0) && report.conversation.map((item, index) => (
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
                            <h5 className="text-sm font-medium text-green-700 mb-2">优点分析</h5>
                            <ul className="space-y-1">
                              {item.ai_feedback.strengths.map((strength, i) => (
                                <li key={i} className="text-sm text-gray-700">• {strength}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <h5 className="text-sm font-medium text-blue-700 mb-2">优化建议</h5>
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