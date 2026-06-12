// 用于提供 components/ui/StreamingMessage.tsx 模块。
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { normalizeAiMarkdown } from '@/lib/markdown'

interface StreamingMessageProps {
  content: string
  isComplete?: boolean
  className?: string
}

// 用于渲染 StreamingMessage 组件。
export default function StreamingMessage({ 
  content, 
  isComplete = false, 
  className = '' 
}: StreamingMessageProps) {
  const displayContent = normalizeAiMarkdown(content)

  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 用于处理h1。
          h1: ({ children }) => <h1 className="text-[18px] font-bold text-gray-900 mb-3">{children}</h1>,
          // 用于处理h2。
          h2: ({ children }) => <h2 className="text-[16px] font-semibold text-gray-900 mb-2">{children}</h2>,
          // 用于处理h3。
          h3: ({ children }) => <h3 className="text-[15px] font-medium text-gray-900 mb-2">{children}</h3>,
          // 用于处理p。
          p: ({ children }) => <p className="text-[14px] text-gray-700 mb-2 last:mb-0">{children}</p>,
          // 用于处理ul。
          ul: ({ children }) => <ul className="list-disc list-inside text-[14px] text-gray-700 mb-2 space-y-1">{children}</ul>,
          // 用于处理ol。
          ol: ({ children }) => <ol className="list-decimal list-inside text-[14px] text-gray-700 mb-2 space-y-1">{children}</ol>,
          // 用于处理li。
          li: ({ children }) => <li className="text-[14px]">{children}</li>,
          // 用于处理code。
          code: ({ children, ...props }) => 
            (props as any).inline ? (
              <code className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-xs font-mono">
                {children}
              </code>
            ) : (
              <code className="block bg-gray-100 text-gray-800 p-3 rounded-lg text-xs font-mono overflow-x-auto">
                {children}
              </code>
            ),
          // 用于处理pre。
          pre: ({ children }) => <pre className="bg-gray-100 p-3 rounded-lg overflow-x-auto mb-2">{children}</pre>,
          // 用于处理blockquote。
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 pl-4 py-2 bg-gray-50 text-[14px] text-gray-600 mb-2 rounded-r">
              {children}
            </blockquote>
          ),
          // 用于处理strong。
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          // 用于处理em。
          em: ({ children }) => <em className="italic text-gray-700">{children}</em>,
          // 用于处理a。
          a: ({ children, href }) => (
            <a 
              href={href} 
              className="text-blue-600 hover:text-blue-800 underline" 
              target="_blank" 
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          // 用于处理table。
          table: ({ children }) => (
            <div className="mb-2 w-full overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full border-collapse text-xs">
                {children}
              </table>
            </div>
          ),
          // 用于处理th。
          th: ({ children }) => (
            <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">
              {children}
            </th>
          ),
          // 用于处理td。
          td: ({ children }) => (
            <td className="border border-gray-200 px-3 py-2 align-top text-gray-700">
              {children}
            </td>
          ),
          // 用于处理img。
          img: ({ src = '', alt = '' }) => (
            <img
              src={src}
              alt={alt as string}
              className="my-2 max-w-[240px] border border-gray-200 rounded-lg shadow-sm"
            />
          ),
        }}
      >
        {displayContent}
      </ReactMarkdown>
      
      {/* 显示流式传输光标 */}
      {!isComplete && content && (
        <span className="inline-block w-0.5 h-4 bg-blue-600 animate-pulse ml-1" />
      )}
    </div>
  )
}
