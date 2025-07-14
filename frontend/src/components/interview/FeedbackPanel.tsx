'use client'

import { useState, useEffect } from 'react'
import { SparklesIcon, LightBulbIcon } from '@heroicons/react/24/outline'
import MarkdownMessage from '@/components/ui/MarkdownMessage'

interface ScoringResult {
  relevance_score: number
  star_analysis: {
    situation: boolean
    task: boolean
    action: boolean
    result: boolean
  }
  keyword_match: {
    matched_tech_keywords: Array<{keyword: string, category: string}>
    matched_jd_keywords: string[]
    tech_coverage: number
    jd_coverage: number
    total_matches: number
  }
  fluency_score: number
  overall_score: number
  suggestions: string[]
}

interface FeedbackPanelProps {
  lastQuestion?: string
  lastAnswer?: string
  resumeId?: number
  isLoading?: boolean
}

export default function FeedbackPanel({ 
  lastQuestion, 
  lastAnswer, 
  resumeId,
  isLoading = false 
}: FeedbackPanelProps) {
  const [scoringResult, setScoringResult] = useState<ScoringResult | null>(null)
  const [isScoring, setIsScoring] = useState(false)

  // 当有新的问答时，自动进行评分
  useEffect(() => {
    if (lastQuestion && lastAnswer && resumeId && !isLoading) {
      scoreAnswer()
    }
  }, [lastQuestion, lastAnswer, resumeId, isLoading])

  const scoreAnswer = async () => {
    if (!lastQuestion || !lastAnswer || !resumeId) return

    setIsScoring(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/interview/score`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: lastQuestion,
          answer: lastAnswer,
          resume_id: resumeId,
          jd_keywords: [] // TODO: 从JD中提取关键词
        })
      })

      if (response.ok) {
        const result = await response.json()
        setScoringResult(result)
      }
    } catch (error) {
      console.error('评分失败:', error)
    } finally {
      setIsScoring(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getScoreBarColor = (score: number) => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getStarIcon = (completed: boolean) => {
    return completed ? '✓' : '○'
  }

  const getStarColor = (completed: boolean) => {
    return completed ? 'text-green-600' : 'text-gray-400'
  }

  return (
    <div className="w-80 bg-gray-50 border-l border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200 bg-white">
        <h3 className="font-semibold text-gray-900 flex items-center">
          <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
          实时反馈
        </h3>
      </div>
      
      <div className="flex-1 p-4 overflow-y-auto">
        {isScoring ? (
          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="text-sm text-gray-600">正在分析回答...</span>
            </div>
          </div>
        ) : scoringResult ? (
          <>
            {/* 综合评分卡片 */}
            <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200 mb-4">
              <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                <SparklesIcon className="w-5 h-5 mr-2 text-blue-500" />
                本次回答分析
              </h4>
              
              {/* 综合评分 */}
              <div className="mb-4 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">综合评分</span>
                  <span className={`text-lg font-bold ${getScoreColor(scoringResult.overall_score)}`}>
                    {Math.round(scoringResult.overall_score)}分
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-500 ${getScoreBarColor(scoringResult.overall_score)}`}
                    style={{width: `${scoringResult.overall_score}%`}}
                  ></div>
                </div>
              </div>
              
              {/* 多维度评分 */}
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">内容相关性</span>
                    <span className={`text-sm font-medium ${getScoreColor(scoringResult.relevance_score)}`}>
                      {Math.round(scoringResult.relevance_score)}分
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-300 ${getScoreBarColor(scoringResult.relevance_score)}`}
                      style={{width: `${scoringResult.relevance_score}%`}}
                    ></div>
                  </div>
                </div>
                
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">STAR法则应用</span>
                    <span className="text-sm">
                      <span className={getStarColor(scoringResult.star_analysis.situation)}>{getStarIcon(scoringResult.star_analysis.situation)}</span>S 
                      <span className={`ml-1 ${getStarColor(scoringResult.star_analysis.task)}`}>{getStarIcon(scoringResult.star_analysis.task)}</span>T 
                      <span className={`ml-1 ${getStarColor(scoringResult.star_analysis.action)}`}>{getStarIcon(scoringResult.star_analysis.action)}</span>A 
                      <span className={`ml-1 ${getStarColor(scoringResult.star_analysis.result)}`}>{getStarIcon(scoringResult.star_analysis.result)}</span>R
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    情境 · 任务 · 行动 · 结果
                  </div>
                </div>
                
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">关键词覆盖</span>
                    <span className="text-sm text-blue-600">{Math.round(scoringResult.keyword_match.tech_coverage)}%</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {scoringResult.keyword_match.matched_tech_keywords.slice(0, 6).map((item, index) => (
                      <span key={index} className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                        {item.keyword}
                      </span>
                    ))}
                    {scoringResult.keyword_match.matched_tech_keywords.length > 6 && (
                      <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                        +{scoringResult.keyword_match.matched_tech_keywords.length - 6}
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">表达流畅度</span>
                    <span className={`text-sm font-medium ${getScoreColor(scoringResult.fluency_score)}`}>
                      {Math.round(scoringResult.fluency_score)}分
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-300 ${getScoreBarColor(scoringResult.fluency_score)}`}
                      style={{width: `${scoringResult.fluency_score}%`}}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* 优化建议卡片 */}
            {scoringResult.suggestions.length > 0 && (
              <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                  <LightBulbIcon className="w-5 h-5 mr-2 text-yellow-500" />
                  优化建议
                </h4>
                <div className="space-y-2">
                  {scoringResult.suggestions.map((suggestion, index) => (
                    <div key={index} className="flex items-start space-x-2">
                      <span className="w-5 h-5 bg-blue-100 text-blue-600 text-xs rounded-full flex items-center justify-center mt-0.5 flex-shrink-0">
                        {index + 1}
                      </span>
                      <div className="text-sm text-gray-700 leading-relaxed">
                        <MarkdownMessage content={suggestion} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="text-center py-8">
              <SparklesIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <h4 className="font-medium text-gray-900 mb-2">等待回答分析</h4>
              <p className="text-sm text-gray-500">
                回答问题后，这里将显示详细的分析和建议
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}