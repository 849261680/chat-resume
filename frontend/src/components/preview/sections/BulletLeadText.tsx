// 用于提供简历要点前缀加粗渲染。

const LEAD_LABEL_PATTERN = /^([^：:]{1,40})([：:])(.+)$/

interface BulletLeadTextProps {
  text: string
}

// 用于把 bullet 第一个冒号前的要点标签加粗。
export default function BulletLeadText({ text }: BulletLeadTextProps) {
  const match = text.match(LEAD_LABEL_PATTERN)
  if (!match) return <>{text}</>

  const [, label, colon, rest] = match
  return (
    <>
      <strong className="font-semibold">{label}{colon}</strong>
      {rest}
    </>
  )
}
