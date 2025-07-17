// 简历内容接口定义
interface PersonalInfo {
  name?: string
  email?: string
  phone?: string
  position?: string
  github?: string
}

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
}

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
}

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface Project {
  id?: number
  name: string
  description: string
  technologies: string[]
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  achievements: string[]
}

interface ResumeContent {
  parsing_quality?: number
  parsing_method?: string
  personal_info?: PersonalInfo
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
}

interface Resume {
  id: number
  title: string
  content: ResumeContent
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
}

interface CreateResumeData {
  title: string
  content: ResumeContent
}

interface UpdateResumeData {
  title?: string
  content?: ResumeContent
}

// 面试相关类型
interface InterviewSession {
  id: number
  resume_id: number
  resume_title?: string
  job_position: string
  interview_mode: string
  jd_content: string
  questions: any[]
  answers: any[]
  feedback: any
  status: string
  overall_score?: number
  current_question?: number
  total_questions?: number
  created_at: string
  updated_at: string
}

interface InterviewConfig {
  job_position: string
  interview_mode: string
  jd_content?: string
  question_count?: number
}

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 获取认证头部信息
function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// 处理API响应
async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `API请求失败: ${response.status}`)
  }
  
  return response.json()
}

// 简历API类
class ResumeAPI {
  /**
   * 获取所有简历
   */
  static async getResumes(): Promise<Resume[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/`, {
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<Resume[]>(response)
  }

  /**
   * 获取单个简历
   */
  static async getResume(id: number): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${id}`, {
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 创建新简历
   */
  static async createResume(data: CreateResumeData): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 更新简历
   */
  static async updateResume(id: number, data: UpdateResumeData): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 删除简历
   */
  static async deleteResume(id: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${id}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除简历失败: ${response.status}`)
    }
  }

  /**
   * 上传简历文件
   */
  static async uploadResume(file: File): Promise<Resume> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE_URL}/api/v1/upload/resume`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
      body: formData,
    })

    return handleApiResponse<Resume>(response)
  }
}

// 聊天API类
class ChatAPI {
  /**
   * 发送聊天消息（非流式）
   */
  static async sendMessage(resumeId: number, message: string, chatHistory: any[] = []): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/v1/ai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        message,
        resume_id: resumeId,
        chat_history: chatHistory,
      }),
    })

    const data = await handleApiResponse<{ response: string }>(response)
    return data.response
  }

  /**
   * 发送流式聊天消息
   */
  static async sendStreamingMessage(
    resumeId: number,
    message: string,
    chatHistory: any[] = [],
    onChunk: (chunk: string) => void,
    onError: (error: string) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          message,
          resume_id: resumeId,
          chat_history: chatHistory,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `流式聊天失败: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法获取响应流')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        
        // 处理SSE格式的数据
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              return
            }
            
            try {
              const parsed = JSON.parse(data)
              if (parsed.content) {
                onChunk(parsed.content)
              }
              if (parsed.error) {
                onError(parsed.error)
                return
              }
              if (parsed.done) {
                return
              }
            } catch (e) {
              console.warn('解析SSE数据失败:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('流式聊天错误:', error)
      onError(error instanceof Error ? error.message : '流式聊天失败')
    }
  }
}

// 面试API类
class InterviewAPI {
  /**
   * 获取指定简历的面试记录列表
   */
  static async getInterviewSessions(resumeId: number): Promise<InterviewSession[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/sessions`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<InterviewSession[]>(response)
  }

  /**
   * 开始面试会话
   */
  static async startInterview(resumeId: number, config: InterviewConfig): Promise<InterviewSession> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/start`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    })

    return handleApiResponse<InterviewSession>(response)
  }

  /**
   * 结束面试会话
   */
  static async endInterview(resumeId: number, sessionId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/${sessionId}/end`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `结束面试失败: ${response.status}`)
    }
  }

  /**
   * 删除面试会话
   */
  static async deleteInterviewSession(resumeId: number, sessionId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/${sessionId}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除面试记录失败: ${response.status}`)
    }
  }

  /**
   * 为已完成面试计算分数
   */
  static async calculateScoresForCompletedInterviews(resumeId: number): Promise<{message: string, updated_count: number}> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/calculate-scores`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<{message: string, updated_count: number}>(response)
  }

  /**
   * 获取面试详细报告
   */
  static async getInterviewReport(resumeId: number, sessionId: number, regenerate: boolean = false): Promise<any> {
    const params = new URLSearchParams()
    if (regenerate) {
      params.append('regenerate', 'true')
    }
    
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/${sessionId}/report?${params.toString()}`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<any>(response)
  }

  /**
   * 获取下一个面试问题
   */
  static async getNextInterviewQuestion(resumeId: number, sessionId: number): Promise<{
    question: string
    question_type: string
    question_index: number
  }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/${sessionId}/question`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<{
      question: string
      question_type: string
      question_index: number
    }>(response)
  }

  /**
   * 提交面试答案并获取评估
   */
  static async submitInterviewAnswer(resumeId: number, sessionId: number, answer: string, questionIndex: number): Promise<{
    question: string
    answer: string
    evaluation: any
    score: number
    feedback: string
    suggestions: string[]
  }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}/interview/${sessionId}/answer`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        answer,
        question_index: questionIndex
      }),
    })

    return handleApiResponse<{
      question: string
      answer: string
      evaluation: any
      score: number
      feedback: string
      suggestions: string[]
    }>(response)
  }
}

// 导出API实例
export const resumeApi = ResumeAPI
export const chatApi = ChatAPI
export const interviewApi = InterviewAPI

// 导出类型
export type {
  Resume,
  ResumeContent,
  PersonalInfo,
  Education,
  WorkExperience,
  Skill,
  Project,
  CreateResumeData,
  UpdateResumeData,
  InterviewSession,
  InterviewConfig,
}