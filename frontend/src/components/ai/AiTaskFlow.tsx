import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ClipboardCopy, Loader2, RotateCcw, Wrench } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { AiTask, AiTaskType } from '@/api/types'
import { ErrorText, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { isWarning } from '@/lib/ai'
import { cn } from '@/lib/utils'

export function useAiSettings() {
  return useQuery({ queryKey: ['ai-settings'], queryFn: () => api.get<import('@/api/types').AiSettings>('/api/ai/settings') })
}

export function CopyButton({ text, label = 'Copy prompt' }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard blocked: select the text so Ctrl+C works.
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }
    setDone(true)
    setTimeout(() => setDone(false), 2000)
  }
  return (
    <Button type="button" variant="outline" size="sm" onClick={copy}>
      {done ? <Check className="size-4" /> : <ClipboardCopy className="size-4" />} {done ? 'Copied' : label}
    </Button>
  )
}

interface Props {
  task: AiTaskType
  jobId?: number
  resumeText?: string
  provider: 'copy_paste' | 'ollama'
  /** Rendered once the reply is valid: the task's review screen. */
  children: (t: AiTask) => ReactNode
}

/**
 * The shared AI flow (brief §6.6): build prompt -> copy -> paste reply -> check (tolerant parser + schema +
 * fabrication guard) -> review. With Ollama the reply arrives by itself; on failure the same prompt can be used
 * with Copy-Paste instead.
 */
export default function AiTaskFlow({ task, jobId, resumeText, provider, children }: Props) {
  const qc = useQueryClient()
  const started = useRef(false)
  const [taskId, setTaskId] = useState<number | null>(null)
  const [reply, setReply] = useState('')
  const [manual, setManual] = useState(provider === 'copy_paste') // show the copy/paste steps
  const [fixup, setFixup] = useState('')
  const [elapsed, setElapsed] = useState(0)

  const create = useMutation({
    mutationFn: () => api.post<AiTask>('/api/ai/tasks', { task, job_id: jobId ?? null, resume_text: resumeText ?? '', provider }),
    onSuccess: (t) => { setTaskId(t.id); qc.setQueryData(['ai-task', t.id], t) },
  })
  useEffect(() => {
    if (!started.current) { started.current = true; create.mutate() }
  }, [create])

  const q = useQuery({
    queryKey: ['ai-task', taskId],
    queryFn: () => api.get<AiTask>(`/api/ai/tasks/${taskId}`),
    enabled: taskId !== null,
    refetchInterval: (s) => (s.state.data?.status === 'running' ? 1000 : false),
  })
  const t = q.data
  const running = t?.status === 'running'
  useEffect(() => {
    if (!running) return
    const start = Date.now()
    setElapsed(0)
    const id = setInterval(() => setElapsed(Math.round((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(id)
  }, [running])

  const set = (next: AiTask) => qc.setQueryData(['ai-task', next.id], next)
  const check = useMutation({ mutationFn: () => api.post<AiTask>(`/api/ai/tasks/${taskId}/reply`, { reply }), onSuccess: (n) => { set(n); setFixup('') } })
  const getFixup = useMutation({ mutationFn: () => api.get<{ prompt: string }>(`/api/ai/tasks/${taskId}/fixup`), onSuccess: (r) => setFixup(r.prompt) })
  const retry = useMutation({ mutationFn: () => api.post<AiTask>(`/api/ai/tasks/${taskId}/run-ollama`), onSuccess: set })
  const settings = useAiSettings()

  if (create.isPending || (!t && !create.error)) return <p className="text-sm text-muted-foreground">Building the prompt…</p>
  if (create.error) return <ErrorText error={create.error} />
  if (!t) return <ErrorText error={q.error} />

  const parsed = t.status === 'parsed' || t.status === 'saved'
  const amber = t.flags.filter(isWarning).length
  const red = t.flags.length - amber

  return (
    <div className="flex flex-col gap-4">
      {t.provider === 'ollama' && running && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/40 px-3 py-3 text-[15px]">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
          <div>
            <div className="font-medium">Asking {settings.data?.ollama_model ?? 'Ollama'} on this laptop… {elapsed} s</div>
            <div className="text-sm text-muted-foreground">The first run loads the model and can take a minute or two. You can close this and come back.</div>
          </div>
        </div>
      )}
      {t.status === 'failed' && (
        <Notice tone="warn">
          <div className="flex flex-col gap-2">
            <span><strong>Ollama couldn't finish:</strong> {t.error_message}</span>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => retry.mutate()} disabled={retry.isPending}><RotateCcw className="size-4" /> Try Ollama again</Button>
              <Button size="sm" variant="outline" onClick={() => setManual(true)}>Use Copy-Paste instead</Button>
            </div>
            <ErrorText error={retry.error} />
          </div>
        </Notice>
      )}

      {(manual || t.status === 'invalid') && !parsed && (
        <>
          <section className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-medium">1. Copy the prompt</h3>
              <CopyButton text={t.prompt} />
            </div>
            <Textarea readOnly rows={7} value={t.prompt} className="font-mono text-xs" aria-label="Prompt" />
            <p className="text-sm text-muted-foreground">Paste it into a free web chat (ChatGPT, Claude or Gemini), then copy the chat's whole reply.</p>
          </section>
          <section className="flex flex-col gap-2">
            <h3 className="font-medium">2. Paste the reply</h3>
            <Textarea rows={7} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Paste the chat's reply here (the ```json block, or the whole message)" aria-label="Reply" className="font-mono text-xs" />
            <div className="flex items-center justify-end gap-2">
              <ErrorText error={check.error} />
              <Button disabled={!reply.trim() || check.isPending} onClick={() => check.mutate()}>{check.isPending ? 'Checking…' : 'Check reply'}</Button>
            </div>
          </section>
        </>
      )}

      {t.status === 'invalid' && t.errors.length > 0 && (
        <div className="rounded-lg border border-danger-edge bg-danger-bg px-3 py-2 text-sm text-danger">
          <div className="mb-1 font-medium">The reply doesn't match the format yet. Fix it above and check again, or ask the chat to fix it:</div>
          <ul className="mb-2 list-disc pl-5">
            {t.errors.map((e, i) => <li key={i}><code className="font-mono">{e.path}</code>: {e.message}</li>)}
          </ul>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => getFixup.mutate()} disabled={getFixup.isPending}><Wrench className="size-4" /> Generate fix-up prompt</Button>
            {fixup && <CopyButton text={fixup} label="Copy fix-up prompt" />}
          </div>
          {fixup && <Textarea readOnly rows={5} value={fixup} className="mt-2 bg-background font-mono text-xs" aria-label="Fix-up prompt" />}
          <ErrorText error={getFixup.error} />
        </div>
      )}

      {parsed && t.result && (
        <>
          {(t.repairs.length > 0 || t.flags.length > 0) && (
            <div className={cn('rounded-lg px-3 py-2 text-sm', red ? 'border border-danger-edge bg-danger-bg text-danger' : amber ? 'border border-attention-edge bg-attention-bg text-attention' : 'bg-muted')}>
              {red > 0 && <div className="font-medium">{red} item{red === 1 ? '' : 's'} flagged in red: possibly invented (an ID, skill or number that isn't in your bank or profile). Check each one.</div>}
              {amber > 0 && <div className="font-medium text-attention">{amber} in amber: worth a look (a skill not in that bullet's bank item, a repeated title/date removed, or several bullets in one).</div>}
              {t.repairs.length > 0 && <div className="text-muted-foreground">Fixed in the reply automatically: {t.repairs.join(', ')}.</div>}
            </div>
          )}
          {children(t)}
          {t.provider === 'copy_paste' && t.status !== 'saved' && (
            <button className="self-start text-sm text-muted-foreground underline" onClick={() => { setReply(t.response); qc.setQueryData(['ai-task', t.id], { ...t, status: 'invalid', errors: [] }) }}>
              Paste a different reply
            </button>
          )}
        </>
      )}
    </div>
  )
}
