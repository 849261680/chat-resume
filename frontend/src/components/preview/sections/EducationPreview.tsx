'use client'

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
}

interface EducationPreviewProps {
  data: Education[]
}

export default function EducationPreview({ data }: EducationPreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
        教育背景
      </h2>
      
      <div className="space-y-4">
        {data.map((edu, index) => (
          <div key={edu.id || index} className="relative">
            <div className="flex justify-between items-start mb-2">
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {edu.school}
                </h3>
                <p className="text-gray-700">
                  {edu.major} · {edu.degree}
                </p>
              </div>
              <div className="text-sm text-gray-600 ml-4">
                {edu.duration}
              </div>
            </div>
            
            {edu.description && (
              <p className="text-sm text-gray-600 mt-2">
                {edu.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}