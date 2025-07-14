'use client'

interface QuestionType {
  id: string
  label: string
  color: string
  bgColor: string
  description: string
  icon: string
}

const questionTypes: QuestionType[] = [
  {
    id: 'introduction',
    label: '自我介绍',
    color: 'text-blue-700',
    bgColor: 'bg-blue-100',
    description: '了解候选人的基本背景和经验',
    icon: '👋'
  },
  {
    id: 'technical',
    label: '技术基础',
    color: 'text-purple-700',
    bgColor: 'bg-purple-100',
    description: '验证技术知识和理解深度',
    icon: '⚡'
  },
  {
    id: 'project',
    label: '项目深挖',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
    description: '深入了解项目经验和解决方案',
    icon: '🚀'
  },
  {
    id: 'behavioral',
    label: '行为问题',
    color: 'text-orange-700',
    bgColor: 'bg-orange-100',
    description: '评估软技能和团队协作能力',
    icon: '🤝'
  },
  {
    id: 'scenario',
    label: '场景题',
    color: 'text-red-700',
    bgColor: 'bg-red-100',
    description: '测试解决实际问题的思路',
    icon: '💡'
  },
  {
    id: 'culture',
    label: '文化匹配',
    color: 'text-indigo-700',
    bgColor: 'bg-indigo-100',
    description: '了解价值观和工作方式',
    icon: '🎯'
  }
]

interface QuestionTypeLabelProps {
  type: string
  showDescription?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export default function QuestionTypeLabel({ 
  type, 
  showDescription = false, 
  size = 'md' 
}: QuestionTypeLabelProps) {
  const questionType = questionTypes.find(qt => qt.id === type) || questionTypes[0]
  
  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base'
  }

  return (
    <div className={`inline-flex items-center ${questionType.bgColor} ${questionType.color} rounded-full font-medium ${sizeClasses[size]}`}>
      <span className="mr-1">{questionType.icon}</span>
      <span>{questionType.label}</span>
      {showDescription && (
        <span className="ml-2 text-xs opacity-75">
          {questionType.description}
        </span>
      )}
    </div>
  )
}

// 自动检测问题类型的函数
export function detectQuestionType(questionText: string): string {
  const text = questionText.toLowerCase()
  
  if (text.includes('自我介绍') || text.includes('介绍一下') || text.includes('简单介绍')) {
    return 'introduction'
  }
  
  if (text.includes('技术') || text.includes('算法') || text.includes('数据结构') || 
      text.includes('编程') || text.includes('代码') || text.includes('框架')) {
    return 'technical'
  }
  
  if (text.includes('项目') || text.includes('经验') || text.includes('开发') || 
      text.includes('实现') || text.includes('架构') || text.includes('设计')) {
    return 'project'
  }
  
  if (text.includes('团队') || text.includes('协作') || text.includes('沟通') || 
      text.includes('领导') || text.includes('冲突') || text.includes('困难')) {
    return 'behavioral'
  }
  
  if (text.includes('如果') || text.includes('假设') || text.includes('场景') || 
      text.includes('遇到') || text.includes('处理') || text.includes('解决')) {
    return 'scenario'
  }
  
  if (text.includes('公司') || text.includes('文化') || text.includes('价值观') || 
      text.includes('为什么') || text.includes('期望') || text.includes('目标')) {
    return 'culture'
  }
  
  return 'technical' // 默认类型
}

export { questionTypes }
export type { QuestionType }