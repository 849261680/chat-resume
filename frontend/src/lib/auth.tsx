'use client'
// 用于提供 lib/auth.tsx 模块。

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { apiFetch, handleApiResponse } from './httpClient'
import zhAuth from '../../locales/zh/auth.json'
import enAuth from '../../locales/en/auth.json'

// 用户接口定义
interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  has_password?: boolean
  created_at: string
}

// 登录响应接口
interface LoginResponse {
  token_type: string
  user: User
}

// 注册请求接口
interface RegisterRequest {
  email: string
  password: string
  full_name?: string
}

// 认证上下文接口
interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<boolean>
  register: (email: string, password: string) => Promise<boolean>
  logout: () => void
  updateUser: (userData: Partial<User>) => void
  refreshUser: () => Promise<void>
}

// 创建认证上下文
const AuthContext = createContext<AuthContextType | undefined>(undefined)

const USER_STORAGE_KEY = 'auth_user'

// 用于获取认证消息。
function currentAuthMessages() {
  // Chooses fallback auth copy without tying the auth client to React hooks.
  const locale = document.cookie.includes('NEXT_LOCALE=en') ? 'en' : 'zh'
  return locale === 'en' ? enAuth : zhAuth
}

// 用于处理认证消息。
function authMessage(key: 'login' | 'register' | 'getCurrentUser' | 'refresh' | 'logout') {
  // Maps low-level auth failures to localized fallback messages.
  const messages = currentAuthMessages()
  const errors = {
    login: messages.errors.loginFailed,
    register: messages.errors.registerFailed,
    getCurrentUser: messages.errors.getCurrentUserFailed,
    refresh: messages.errors.refreshFailed,
    logout: messages.errors.logoutFailed,
  }
  return errors[key]
}

// 用于判断认证失败是否属于用户可恢复状态，不作为异常噪声输出。
function isExpectedAuthError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  return message === 'Not authenticated'
    || message === 'Invalid refresh token'
    || message === 'Incorrect email or password'
    || message === authMessage('getCurrentUser')
    || message === authMessage('refresh')
}


// 用于读取本地用户用户。
function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

// 用于写入本地用户用户。
function writeStoredUser(user: User | null) {
  if (!user) {
    localStorage.removeItem(USER_STORAGE_KEY)
    return
  }
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
}

// 认证相关API调用
class AuthAPI {
  // 用于处理登录。
  static async login(email: string, password: string): Promise<LoginResponse> {
    const response = await apiFetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    })

    return handleApiResponse<LoginResponse>(response, authMessage('login'))
  }

  // 用于处理register。
  static async register(data: RegisterRequest): Promise<User> {
    const response = await apiFetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<User>(response, authMessage('register'))
  }

  // 用于获取current用户。
  static async getCurrentUser(): Promise<User> {
    const response = await apiFetch('/api/auth/me')
    return handleApiResponse<User>(response, authMessage('getCurrentUser'))
  }

  // 用于处理refresh。
  static async refresh(): Promise<LoginResponse> {
    const response = await apiFetch('/api/auth/refresh', {
      method: 'POST',
    })

    return handleApiResponse<LoginResponse>(response, authMessage('refresh'))
  }

  // 用于处理logout。
  static async logout(): Promise<void> {
    const response = await apiFetch('/api/auth/logout', {
      method: 'POST',
    })

    await handleApiResponse<void>(response, authMessage('logout'))
  }
}

// 认证提供者组件
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user

  // 登录函数
  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await AuthAPI.login(email, password)

      // 设置用户信息
      setUser(response.user)
      writeStoredUser(response.user)
      
      return true
    } catch (error) {
      if (!isExpectedAuthError(error)) {
        console.error('Login error:', error)
      }
      throw error
    }
  }

  // 注册函数
  const register = async (email: string, password: string): Promise<boolean> => {
    try {
      await AuthAPI.register({
        email,
        password,
      })
      
      // 注册成功后自动登录
      return await login(email, password)
    } catch (error) {
      console.error('Register error:', error)
      return false
    }
  }

  // 登出函数
  const logout = () => {
    localStorage.removeItem(USER_STORAGE_KEY)
    setUser(null)
    AuthAPI.logout().catch((error) => {
      console.error('Logout error:', error)
    })
  }

  // 用于处理refresh会话。
  const refreshSession = async (): Promise<boolean> => {
    try {
      const response = await AuthAPI.refresh()
      setUser(response.user)
      writeStoredUser(response.user)
      return true
    } catch (error) {
      if (!isExpectedAuthError(error)) {
        console.error('Refresh session error:', error)
      }
      localStorage.removeItem(USER_STORAGE_KEY)
      setUser(null)
      AuthAPI.logout().catch((logoutError) => {
        if (!isExpectedAuthError(logoutError)) {
          console.error('Logout after refresh failure error:', logoutError)
        }
      })
      return false
    }
  }

  // 更新用户信息
  const updateUser = (userData: Partial<User>) => {
    if (user) {
      const nextUser = { ...user, ...userData }
      setUser(nextUser)
      writeStoredUser(nextUser)
    }
  }

  // 刷新用户信息
  const refreshUser = async () => {
    try {
      const freshUser = await AuthAPI.getCurrentUser().catch(async () => {
        const refreshed = await refreshSession()
        if (!refreshed) {
          throw new Error(authMessage('getCurrentUser'))
        }
        return AuthAPI.getCurrentUser()
      })
      setUser(freshUser)
      writeStoredUser(freshUser)
    } catch (error) {
      if (!isExpectedAuthError(error)) {
        console.error('Refresh user error:', error)
      }
      localStorage.removeItem(USER_STORAGE_KEY)
      setUser(null)
    }
  }

  // 检查认证状态
  const checkAuth = async () => {
    try {
      const cachedUser = readStoredUser()
      if (cachedUser) {
        setUser(cachedUser)
      }

      const user = await AuthAPI.getCurrentUser().catch(async () => {
        const refreshed = await refreshSession()
        if (!refreshed) {
          throw new Error(authMessage('getCurrentUser'))
        }
        return AuthAPI.getCurrentUser()
      })
      setUser(user)
      writeStoredUser(user)
    } catch (error) {
      if (!isExpectedAuthError(error)) {
        console.error('Auth check error:', error)
      }
      localStorage.removeItem(USER_STORAGE_KEY)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuth()
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    updateUser,
    refreshUser,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// 使用认证的Hook
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
