'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { UserIcon } from '@heroicons/react/24/outline'
import { DocumentIcon } from '@heroicons/react/24/solid'
import { useAuth } from '@/lib/auth'

export default function MainNavigation() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  const navItems = [
    { name: '简历中心', href: '/dashboard' },
    { name: '面试中心', href: '/interviews' }
  ]

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          {/* Logo和品牌 */}
          <div className="flex items-center space-x-8">
            <Link href="/dashboard" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                <DocumentIcon className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Chat Resume</span>
            </Link>

            {/* 主导航 */}
            <nav className="hidden md:flex space-x-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href || 
                  (item.href === '/dashboard' && pathname.startsWith('/resume')) ||
                  (item.href === '/interviews' && pathname.startsWith('/interview'))

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-100 text-blue-700 border border-blue-200'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    <span>{item.name}</span>
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* 用户信息和操作 */}
          <div className="flex items-center space-x-4">
            {/* 移动端导航 */}
            <nav className="md:hidden flex space-x-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href || 
                  (item.href === '/dashboard' && pathname.startsWith('/resume')) ||
                  (item.href === '/interviews' && pathname.startsWith('/interview'))

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-100 text-blue-700 border border-blue-200'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    <span>{item.name}</span>
                  </Link>
                )
              })}
            </nav>

            {/* 用户下拉菜单 */}
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                  <UserIcon className="w-5 h-5 text-gray-600" />
                </div>
                <div className="hidden sm:block">
                  <span className="text-sm font-medium text-gray-900">
                    {user?.full_name || 'User'}
                  </span>
                  <div className="text-xs text-gray-500">
                    {user?.email}
                  </div>
                </div>
              </div>

              <button
                onClick={logout}
                className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1 rounded-md hover:bg-gray-50 transition-colors"
              >
                退出
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}