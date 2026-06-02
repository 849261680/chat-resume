// 用于提供 types/resume.ts 模块。
export interface ResumeBullet {
  id?: string
  text: string
}

export type ResumeHighlight = ResumeBullet

interface ResumeLink {
  id?: string
  label: string
  url: string
}

interface ResumeMeta {
  schema_version?: string
  language?: string
  target_role?: string
}

export interface JobApplication {
  target_title?: string
  target_company?: string
  jd_text?: string
  strategy?: string
}

export interface PersonalInfo {
  name?: string
  photo_url?: string
  email?: string
  phone?: string
  position?: string
  headline?: string
  location?: string
  github?: string
  linkedin?: string
  website?: string
  address?: string
  links?: ResumeLink[]
}

interface Summary {
  text?: string
}

export interface Education {
  id?: string
  school: string
  major: string
  degree: string
  duration: string
  start_date?: string
  end_date?: string
  location?: string
  gpa?: string
  description?: string
  highlights?: ResumeBullet[]
}

export interface WorkExperience {
  id?: string
  company: string
  position: string
  duration: string
  start_date?: string
  end_date?: string
  is_current?: boolean
  location?: string
  employment_type?: string
  highlights?: ResumeBullet[]
  technologies?: string[]
}

export interface Skill {
  id?: string
  category: string
  items: string[]
}

export interface Project {
  id?: string
  name: string
  overview?: string
  description?: string
  summary?: string
  technologies?: string[]
  role: string
  duration: string
  start_date?: string
  end_date?: string
  github_url?: string
  demo_url?: string
  achievements?: string[]
  highlights?: ResumeBullet[]
  links?: ResumeLink[]
}

export type OpenSourceContribution = Project

interface Language {
  id?: string
  name: string
  level: string
}

interface CustomSection {
  id?: string
  title: string
  content: string
}

export interface ResumeContent {
  meta?: ResumeMeta
  parsing_quality?: number
  parsing_method?: string
  job_application?: JobApplication
  personal_info?: PersonalInfo
  summary?: Summary
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
  open_source?: OpenSourceContribution[]
  languages?: Language[]
  custom_sections?: CustomSection[]
}
