import { Check } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import PreferredLocations from '@/components/PreferredLocations'
import { educationLabel, useProfileStatus } from '@/lib/profile'
import ResumeUpload from '@/components/ResumeUpload'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { ProfileTab } from './Settings'
import { writeLocal } from '@/lib/storage'

export const SETUP_DONE_KEY = 'setupDone'

const STEPS = [
  { title: 'Profile', desc: 'The basics the score needs: years of experience, education and the languages you speak.' },
  { title: 'Resume', desc: 'Upload your resume and check what was read. It becomes your Experience Bank.' },
  { title: 'Preferred locations', desc: 'Where you want to work. Pick states, towns or Remote.' },
  { title: 'Done', desc: '' },
]

export default function Setup() {
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const finish = (to: string) => {
    writeLocal(SETUP_DONE_KEY, '1')
    navigate(to)
  }
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1))
  const status = useProfileStatus()
  const missing = status.data?.missing ?? []
  // Which step fixes each missing field
  const STEP_FOR: Record<string, number> = { education_level: 1, education_field: 0, preferred_locations: 2, years_of_experience: 0 }

  return (
    <div className="min-h-screen bg-fog">
      <div className={cn('mx-auto flex flex-col gap-6 px-6 py-8', step === 1 ? 'max-w-7xl' : 'max-w-3xl')}>
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-[26px] leading-tight font-semibold">Set up JobFinder</h1>
            <p className="text-[15px] text-muted-foreground">Four short steps. Everything stays on this laptop, and you can change any of it later in Settings.</p>
          </div>
          <Button variant="ghost" onClick={() => finish('/')}>Skip setup</Button>
        </header>

        <ol className="grid grid-cols-4 gap-2" aria-label="Setup steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <button
                onClick={() => setStep(i)}
                aria-current={i === step ? 'step' : undefined}
                className={cn(
                  'flex w-full items-center gap-2 border-t-4 pt-2 text-left text-[15px]',
                  i < step ? 'border-foreground text-foreground' : i === step ? 'border-foreground font-semibold' : 'border-border text-muted-foreground',
                )}
              >
                <span className={cn('flex size-6 shrink-0 items-center justify-center rounded-full text-sm',
                  i < step ? 'bg-foreground text-background' : i === step ? 'border-2 border-foreground text-foreground' : 'border border-input')}>
                  {i < step ? <Check className="size-3.5" /> : i + 1}
                </span>
                {s.title}
              </button>
            </li>
          ))}
        </ol>

        {step < 3 && (
          <div>
            <h2 className="text-xl font-semibold">{STEPS[step].title}</h2>
            <p className="text-[15px] text-muted-foreground">{STEPS[step].desc}</p>
          </div>
        )}

        {step === 0 && (
          <>
            <ProfileTab onSaved={next} saveLabel="Save and continue" />
            <p className="text-sm text-muted-foreground">
              Not sure yet? Skip this step. The resume in the next step can fill your name, contact and education for you.{' '}
              <button className="text-foreground underline underline-offset-2" onClick={next}>Skip this step</button>
            </p>
          </>
        )}
        {step === 1 && (
          <>
            <ResumeUpload onSaved={next} />
            <p className="text-sm text-muted-foreground">
              No resume to hand? <button className="text-foreground underline underline-offset-2" onClick={next}>Skip this step</button>. You can add Experience Bank items by hand later.
            </p>
          </>
        )}
        {step === 2 && (
          <div className="rounded-lg border bg-card p-4"><PreferredLocations onSaved={next} saveLabel="Save and continue" /></div>
        )}
        {step === 3 && (
          <Card>
            <CardContent className="flex flex-col gap-4 py-2">
              {missing.length > 0 ? (
                <>
                  <h2 className="text-xl font-semibold">Almost there</h2>
                  <p className="text-[15px]">The score needs these before it can be trusted. Each takes a few seconds.</p>
                  <ul className="flex flex-col gap-2">
                    {missing.map((m) => (
                      <li key={m.key} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-attention-edge bg-attention-bg px-3 py-2 text-attention">
                        <span><span className="font-semibold">{m.label[0].toUpperCase() + m.label.slice(1)}</span>: {m.hint}</span>
                        <Button size="sm" variant="outline" onClick={() => setStep(STEP_FOR[m.key] ?? 0)}>
                          Go to {STEPS[STEP_FOR[m.key] ?? 0].title.toLowerCase()}
                        </Button>
                      </li>
                    ))}
                  </ul>
                  <p className="text-sm text-muted-foreground">You can still leave with “Skip setup” at the top, but scores will be shown with a warning until these are filled in.</p>
                </>
              ) : (
                <>
                  <h2 className="text-xl font-semibold">You're set up</h2>
                  <p className="text-[15px]">
                    Education used for matching: {educationLabel(status.data?.education ?? null)}.
                  </p>
                  <p className="text-[15px]">
                    Next, paste a job you're interested in. JobFinder scores it against your Experience Bank and shows exactly where each point comes from.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => finish('/jobs?import=1')}>Import a job</Button>
                    <Button variant="outline" onClick={() => finish('/')}>Go to the dashboard</Button>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    You can run this setup again from <Link to="/settings" onClick={() => writeLocal(SETUP_DONE_KEY, '1')} className="underline">Settings</Link>.
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
