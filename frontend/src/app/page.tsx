'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { 
  ArrowRightIcon, 
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  CheckIcon
} from '@heroicons/react/24/outline'
import { DocumentIcon } from '@heroicons/react/24/solid'

export default function HomePage() {
  const features = [
    {
      icon: DocumentIcon,
      title: '智能简历解析',
      description: '上传PDF、Word等格式简历，AI自动提取和结构化内容',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50'
    },
    {
      icon: SparklesIcon,
      title: 'AI优化建议',
      description: '根据岗位描述分析匹配度，提供针对性的优化建议',
      color: 'text-purple-600',
      bgColor: 'bg-purple-50'
    },
    {
      icon: ChatBubbleLeftRightIcon,
      title: '模拟面试训练',
      description: '基于简历内容的智能面试问答，提升面试表现',
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    }
  ]

  const steps = [
    { step: '01', title: '上传简历', description: '支持PDF、Word、TXT格式' },
    { step: '02', title: '与AI交流', description: '获得匹配度和优化建议' },
    { step: '03', title: '优化简历', description: '一键应用或手动编辑' },
    { step: '04', title: '模拟面试', description: '练习面试技巧' }
  ]

  const benefits = [
    '提高简历通过率',
    '节省简历制作时间',
    '增强面试自信心',
    '获得专业优化建议',
    '支持多种导出格式'
  ]

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="container-responsive py-4">
        <nav className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
              <DocumentIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Chat Resume</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link href="/login" className="text-gray-600 hover:text-gray-900 transition-colors">
              登录
            </Link>
            <Link href="/register" className="btn-primary">
              免费注册
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="container-responsive py-20">
        <div className="text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              AI驱动的
              <span className="bg-gradient-primary bg-clip-text text-transparent"> 智能简历 </span>
              优化平台
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
              使用先进的AI技术分析简历与岗位匹配度，提供专业优化建议，
              并通过模拟面试训练帮助您获得理想工作
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/login" className="btn-primary btn-lg">
                立即开始
                <ArrowRightIcon className="w-5 h-5 ml-2" />
              </Link>
              <button className="btn-secondary btn-lg">
                观看演示
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="container-responsive py-20 bg-gray-50">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            强大功能，助力求职成功
          </h2>
          <p className="text-lg text-gray-600">
            从简历优化到面试训练，全方位提升您的求职竞争力
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: index * 0.2 }}
              className="card-hover p-8 text-center"
            >
              <div className={`w-16 h-16 ${feature.bgColor} rounded-xl flex items-center justify-center mx-auto mb-6`}>
                <feature.icon className={`w-8 h-8 ${feature.color}`} />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">
                {feature.title}
              </h3>
              <p className="text-gray-600">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="container-responsive py-20">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            使用流程
          </h2>
          <p className="text-lg text-gray-600">
            四个简单步骤，让您的简历脱颖而出
          </p>
        </div>

        <div className="max-w-4xl mx-auto">
          <div className="space-y-8">
            {steps.map((step, index) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="flex items-center space-x-6"
              >
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-primary rounded-full flex items-center justify-center text-white font-bold">
                  {step.step}
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">
                    {step.title}
                  </h3>
                  <p className="text-gray-600">
                    {step.description}
                  </p>
                </div>
                {index < steps.length - 1 && (
                  <ArrowRightIcon className="w-6 h-6 text-gray-400 hidden md:block" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="container-responsive py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              为什么选择 Chat Resume？
            </h2>
          </div>
          
          <div className="grid md:grid-cols-2 gap-8 items-center">
            <div>
              <ul className="space-y-4">
                {benefits.map((benefit, index) => (
                  <motion.li
                    key={benefit}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5, delay: index * 0.1 }}
                    className="flex items-center space-x-3"
                  >
                    <div className="flex-shrink-0 w-6 h-6 bg-success-500 rounded-full flex items-center justify-center">
                      <CheckIcon className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-gray-700">{benefit}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
            <div className="card p-8">
              <div className="text-center">
                <div className="text-4xl font-bold text-primary-600 mb-2">85%</div>
                <div className="text-gray-600 mb-4">用户简历通过率提升</div>
                <div className="text-2xl font-bold text-gray-900 mb-2">3.5倍</div>
                <div className="text-gray-600">面试邀请增长</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container-responsive py-20">
        <div className="bg-gradient-primary rounded-2xl p-12 text-center text-white">
          <h2 className="text-3xl font-bold mb-4">
            准备好提升您的求职竞争力了吗？
          </h2>
          <p className="text-xl mb-8 opacity-90">
            加入数千名成功求职者的行列，让AI助力您的职业发展
          </p>
          <Link href="/register" className="inline-flex items-center px-8 py-4 bg-white text-primary-600 rounded-xl font-semibold hover:bg-gray-50 transition-colors">
            免费开始使用
            <ArrowRightIcon className="w-5 h-5 ml-2" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="container-responsive">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                  <DocumentIcon className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold">Chat Resume</span>
              </div>
              <p className="text-gray-400">
                AI驱动的智能简历优化平台
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-4">产品</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">简历优化</a></li>
                <li><a href="#" className="hover:text-white transition-colors">模拟面试</a></li>
                <li><a href="#" className="hover:text-white transition-colors">简历模板</a></li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">支持</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">帮助中心</a></li>
                <li><a href="#" className="hover:text-white transition-colors">联系我们</a></li>
                <li><a href="#" className="hover:text-white transition-colors">反馈建议</a></li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">公司</h3>
              <ul className="space-y-2 text-gray-400">
                <li><a href="#" className="hover:text-white transition-colors">关于我们</a></li>
                <li><a href="#" className="hover:text-white transition-colors">隐私政策</a></li>
                <li><a href="#" className="hover:text-white transition-colors">服务条款</a></li>
              </ul>
            </div>
          </div>
          <div className="divider border-gray-800"></div>
          <div className="text-center text-gray-400">
            <p>&copy; 2025 Chat Resume. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}