'use client'

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface SkillsPreviewProps {
  data: Skill[]
}

export default function SkillsPreview({ data }: SkillsPreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  // 按技能类别分组
  const skillsByCategory = data.reduce((acc, skill) => {
    if (!acc[skill.category]) {
      acc[skill.category] = []
    }
    acc[skill.category].push(skill)
    return acc
  }, {} as Record<string, Skill[]>)

  const getLevelColor = (level: string) => {
    if (!level) return 'bg-gray-100 text-gray-800'
    
    switch (level.toLowerCase()) {
      case '精通':
      case 'expert':
        return 'bg-green-100 text-green-800'
      case '熟练':
      case 'proficient':
        return 'bg-blue-100 text-blue-800'
      case '了解':
      case 'familiar':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
        技能专长
      </h2>
      
      <div className="space-y-4">
        {Object.entries(skillsByCategory).map(([category, skills]) => (
          <div key={category}>
            <h3 className="font-semibold text-gray-800 mb-2">
              {category}
            </h3>
            <div className="flex flex-wrap gap-2">
              {skills.map((skill, index) => (
                <div 
                  key={skill.id || index}
                  className="flex items-center space-x-2"
                >
                  <span className="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-100 rounded-full">
                    {skill.name}
                  </span>
                  <span className={`px-2 py-1 text-xs rounded ${getLevelColor(skill.level)}`}>
                    {skill.level}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 如果没有分类，则显示简单列表 */}
      {Object.keys(skillsByCategory).length === 1 && Object.keys(skillsByCategory)[0] === '' && (
        <div className="flex flex-wrap gap-2">
          {data.map((skill, index) => (
            <div 
              key={skill.id || index}
              className="flex items-center space-x-2"
            >
              <span className="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-100 rounded-full">
                {skill.name}
              </span>
              <span className={`px-2 py-1 text-xs rounded ${getLevelColor(skill.level)}`}>
                {skill.level}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}