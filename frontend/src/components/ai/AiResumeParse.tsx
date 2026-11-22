import { Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { ExperienceItem, ParseResumeResult, ResumeDraft } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { parsedToDraft } from '@/lib/ai'
import AiTaskFlow, { useAiSettings } from './AiTaskFlow'
import { FlagIcon } from '@/components/common'

/**
 * parse_resume (brief §6.1): for complex layouts, let an AI structure the resume text. The result replaces the
 * draft in the same review screen; nothing is saved until "Save to Experience Bank". Anything the AI wrote that
 * isn't in the resume text is flagged in red.
 */
export default function AiResumeParse({ draft, onDraft }: { draft: ResumeDraft; onDraft: (d: ResumeDraft) => void }) {
  const settings = useAiSettings()
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const [open, setOpen] = useState(false)
  const [n, setN] = useState(0)
  const mode = settings.data?.mode
  if (!mode || mode === 'off') return null
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-3 py-2 text-sm">
      <Sparkles className="size-4 text-muted-foreground" aria-hidden />
      <span className="flex-1">Layout not read well? Let an AI structure it instead ({mode === 'ollama' ? 'Ollama on this laptop' : 'Copy-Paste'}). You still review everything.</span>
      <Button size="sm" variant="outline" onClick={() => { setN(n + 1); setOpen(true) }}>Parse with AI</Button>
      {open && (
        <Dialog open onOpenChange={setOpen}>
          <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle className="text-xl">Parse resume with AI</DialogTitle>
              <DialogDescription className="text-[15px]">The References section was already removed from this text.</DialogDescription>
            </DialogHeader>
            <AiTaskFlow key={n} task="parse_resume" resumeText={draft.raw_text} provider={mode}>
              {(t) => {
                const r = t.result as unknown as ParseResumeResult
                return (
                  <div className="flex flex-col gap-2 text-sm">
                    <div>The AI found <strong>{r.items.length} items</strong>{r.profile.name && <> for <strong>{r.profile.name}</strong></>}.</div>
                    {t.flags.length > 0 && (
                      <ul className="text-danger">{t.flags.map((f, i) => <li key={i}><FlagIcon />{f.path}: {f.message}</li>)}</ul>
                    )}
                    <div className="flex justify-end">
                      <Button onClick={() => { onDraft(parsedToDraft(r, draft, bank.data ?? [])); setOpen(false) }}>Use this in the review screen</Button>
                    </div>
                  </div>
                )
              }}
            </AiTaskFlow>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
