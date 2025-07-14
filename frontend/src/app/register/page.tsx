'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { 
  UserIcon,
  EnvelopeIcon, 
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline'
import { DocumentIcon } from '@heroicons/react/24/solid'

interface RegisterForm {
  fullName: string
  email: string
  password: string
  confirmPassword: string
}

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const { register: registerUser, isLoading } = useAuth()
  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterForm>()
  const router = useRouter()
  
  const password = watch('password')

  const onSubmit = async (data: RegisterForm) => {
    try {
      const success = await registerUser(data.email, data.password, data.fullName)
      if (success) {
        // 注册成功，跳转到仪表板
        router.push('/dashboard')
      }
    } catch (error) {
      console.error('注册失败:', error)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="absolute top-4 left-4">
        <Link href="/" className="flex items-center space-x-2 text-gray-600 hover:text-gray-900">
          <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
            <DocumentIcon className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold">Chat Resume</span>
        </Link>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center"
        >
          <h2 className="text-3xl font-bold text-gray-900 mb-2">
            创建您的账户
          </h2>
          <p className="text-gray-600">
            开始您的智能简历优化之旅
          </p>
        </motion.div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="card p-8"
        >
          <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
            {/* 姓名 */}
            <div>
              <label htmlFor="fullName" className="label">
                姓名
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <UserIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  {...register('fullName', {
                    required: '请输入您的姓名',
                    minLength: { value: 2, message: '姓名至少需要2个字符' }
                  })}
                  type="text"
                  className={`input pl-10 ${errors.fullName ? 'input-error' : ''}`}
                  placeholder="请输入您的姓名"
                />
              </div>
              {errors.fullName && (
                <p className="mt-1 text-sm text-error-600">{errors.fullName.message}</p>
              )}
            </div>

            {/* 邮箱 */}
            <div>
              <label htmlFor="email" className="label">
                邮箱地址
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <EnvelopeIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  {...register('email', {
                    required: '请输入邮箱地址',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: '请输入有效的邮箱地址'
                    }
                  })}
                  type="email"
                  className={`input pl-10 ${errors.email ? 'input-error' : ''}`}
                  placeholder="请输入邮箱地址"
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-sm text-error-600">{errors.email.message}</p>
              )}
            </div>

            {/* 密码 */}
            <div>
              <label htmlFor="password" className="label">
                密码
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <LockClosedIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  {...register('password', {
                    required: '请输入密码',
                    minLength: { value: 6, message: '密码至少需要6个字符' }
                  })}
                  type={showPassword ? 'text' : 'password'}
                  className={`input pl-10 pr-10 ${errors.password ? 'input-error' : ''}`}
                  placeholder="请输入密码"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-error-600">{errors.password.message}</p>
              )}
            </div>

            {/* 确认密码 */}
            <div>
              <label htmlFor="confirmPassword" className="label">
                确认密码
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <LockClosedIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  {...register('confirmPassword', {
                    required: '请确认密码',
                    validate: value => value === password || '两次输入的密码不一致'
                  })}
                  type={showConfirmPassword ? 'text' : 'password'}
                  className={`input pl-10 pr-10 ${errors.confirmPassword ? 'input-error' : ''}`}
                  placeholder="请再次输入密码"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-error-600">{errors.confirmPassword.message}</p>
              )}
            </div>

            {/* 服务条款 */}
            <div className="flex items-center">
              <input
                id="agree-terms"
                type="checkbox"
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                required
              />
              <label htmlFor="agree-terms" className="ml-2 block text-sm text-gray-900">
                我同意
                <a href="#" className="text-primary-600 hover:text-primary-500">
                  服务条款
                </a>
                和
                <a href="#" className="text-primary-600 hover:text-primary-500">
                  隐私政策
                </a>
              </label>
            </div>

            {/* 注册按钮 */}
            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full btn-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? '创建中...' : '创建账户'}
              </button>
            </div>
          </form>

          {/* 登录链接 */}
          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">或者</span>
              </div>
            </div>

            <div className="mt-6 text-center">
              <p className="text-sm text-gray-600">
                已有账户？
                <Link href="/login" className="font-medium text-primary-600 hover:text-primary-500">
                  立即登录
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}