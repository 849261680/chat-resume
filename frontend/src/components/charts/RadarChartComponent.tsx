'use client'

import dynamic from 'next/dynamic'
import { 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  Radar, 
  ResponsiveContainer
} from 'recharts'

interface RadarData {
  subject: string
  A: number
  fullMark: number
}

interface RadarChartComponentProps {
  data: RadarData[]
}

const RadarChartComponent = ({ data }: RadarChartComponentProps) => {
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis 
            angle={18} 
            domain={[0, 100]} 
            tick={{ fontSize: 10 }} 
            tickCount={6}
          />
          <Radar
            name="能力分数"
            dataKey="A"
            stroke="#3B82F6"
            fill="#3B82F6"
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default RadarChartComponent