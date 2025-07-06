'use client'

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
}

interface WorkExperiencePreviewProps {
  data: WorkExperience[]
}

export default function WorkExperiencePreview({ data }: WorkExperiencePreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
        工作经验
      </h2>
      
      <div className="space-y-6">
        {data.map((work, index) => (
          <div key={work.id || index} className="relative">
            <div className="flex justify-between items-start mb-2">
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {work.position}
                </h3>
                <p className="text-gray-700 font-medium">
                  {work.company}
                </p>
              </div>
              <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
                {work.duration}
              </div>
            </div>
            
            {work.description && (
              <div className="text-sm text-gray-600 mt-3">
                {work.description.split('\n').map((line, lineIndex) => (
                  <p key={lineIndex} className="mb-1">
                    {line}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}