import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useProfileStatus } from '@/lib/profile'

/** Amber banner listing key profile fields that are missing, each linking to where it is fixed. */
export default function ProfileGaps({ context = 'scores' }: { context?: 'scores' | 'score' }) {
  const q = useProfileStatus()
  const missing = q.data?.missing ?? []
  if (missing.length === 0) return null
  return (
    <div role="status" className="flex gap-3 rounded-lg border border-attention-edge bg-attention-bg px-4 py-3 text-attention">
      <AlertTriangle className="mt-0.5 size-5 shrink-0" />
      <div className="text-[15px]">
        <p className="font-semibold">
          {context === 'score' ? 'This score may be off.' : 'Scores may be off.'} Your profile is missing{' '}
          {missing.map((m) => m.label).join(', ').replace(/, ([^,]*)$/, ' and $1')}.
        </p>
        <ul className="mt-1 flex flex-col gap-0.5 text-sm">
          {missing.map((m) => (
            <li key={m.key}>
              <Link to={m.fix} className="font-medium underline">Add {m.label}</Link>
              <span className="text-attention/80">: {m.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
