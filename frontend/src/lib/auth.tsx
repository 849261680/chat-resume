'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'

// 用户接口定义
interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  created_at: string
}

// 登录响应接口
interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

// 注册请求接口
interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

// 认证上下文接口
interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<boolean>
  register: (email: string, password: string, fullName: string) => Promise<boolean>
  logout: () => void
}

// 创建认证上下文
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 认证相关API调用
class AuthAPI {
  private static getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('access_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  static async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '登录失败')
    }

    return response.json()
  }

  static async register(data: RegisterRequest): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '注册失败')
    }

    return response.json()
  }

  static async getCurrentUser(): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
      headers: {
        ...this.getAuthHeaders(),
      },
    })

    if (!response.ok) {
      throw new Error('获取用户信息失败')
    }

    return response.json()
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
      
      // 保存token到localStorage
      localStorage.setItem('access_token', response.access_token)
      
      // 设置用户信息
      setUser(response.user)
      
      return true
    } catch (error) {
      console.error('Login error:', error)
      // 抛出错误以便上层处理
      throw error
    }
  }

  // 注册函数
  const register = async (email: string, password: string, fullName: string): Promise<boolean> => {
    try {
      const user = await AuthAPI.register({
        email,
        password,
        full_name: fullName,
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
    localStorage.removeItem('access_token')
    setUser(null)
  }

  // 检查认证状态
  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token')
      
      if (!token) {
        setIsLoading(false)
        return
      }

      const user = await AuthAPI.getCurrentUser()
      setUser(user)
    } catch (error) {
      console.error('Auth check error:', error)
      // 如果token无效，清除它
      localStorage.removeItem('access_token')
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