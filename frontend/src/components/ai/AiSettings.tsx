import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { AiSettings, OllamaStatus, PromptTemplate } from '@/api/types'
import { ErrorText, Field, NativeSelect } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { TASK_LABEL } from '@/lib/ai'
import { cn } from '@/lib/utils'
import { useLocalCopy } from '@/lib/hooks'

const MODES = [
  { value: 'copy_paste', label: 'Copy-Paste (default): copy a prompt into a free web chat, paste the reply back' },
  { value: 'ollama', label: 'Ollama: run a small local model on this laptop automatically' },
  { value: 'off', label: 'Off: hide AI features (matching, tracking and the template cover letter still work)' },
]

export function AiSettingsTab() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['ai-settings'], queryFn: () => api.get<AiSettings>('/api/ai/settings') })
  const [s, setS] = useLocalCopy<AiSettings | null>(q.data ?? null)
  const save = useMutation({ mutationFn: (v: AiSettings) => api.put<AiSettings>('/api/ai/settings', v), onSuccess: (v) => qc.setQueryData(['ai-settings'], v) })
  const status = useMutation({ mutationFn: (model: string) => api.get<OllamaStatus>(`/api/ai/ollama/status?model=${encodeURIComponent(model)}`) })
  if (!s) return <ErrorText error={q.error} />
  const st = status.data
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <Field label="AI mode">
          <NativeSelect className="h-9" value={s.mode} onChange={(v) => setS({ ...s, mode: v as AiSettings['mode'] })} options={MODES} />
        </Field>
        <p className="text-sm text-muted-foreground">There is no paid AI service. Copy-Paste sends nothing by itself: you copy the prompt out. Ollama talks only to localhost:11434.</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Ollama model">
            <Input value={s.ollama_model} onChange={(e) => setS({ ...s, ollama_model: e.target.value })} placeholder="qwen2.5:3b" />
          </Field>
          <Field label="Ollama timeout (seconds)">
            <Input type="number" min={30} max={1800} value={s.ollama_timeout_s} onChange={(e) => setS({ ...s, ollama_timeout_s: Number(e.target.value) })} />
          </Field>
          <Field label="Automatic deep analyses per run">
            <Input type="number" min={1} max={20} value={s.auto_analysis_max_per_run} onChange={(e) => setS({ ...s, auto_analysis_max_per_run: Number(e.target.value) })} />
          </Field>
        </div>
        <p className="text-sm text-muted-foreground">Small models (3B–4B, e.g. qwen2.5:3b or llama3.2:3b) fit a 3 GB GPU. Install one with <code className="rounded bg-muted px-1">ollama pull qwen2.5:3b</code>.</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => status.mutate(s.ollama_model)} disabled={status.isPending}>{status.isPending ? 'Checking…' : 'Check Ollama'}</Button>
          {st && (
            <span className={cn('flex items-center gap-1.5 text-sm', st.running && st.installed ? 'text-foreground' : 'text-attention')}>
              {st.running && st.installed ? <CheckCircle2 className="size-4" /> : <CircleAlert className="size-4" />}
              {st.message}{st.running && st.models.length > 0 && ` Installed: ${st.models.join(', ')}.`}
            </span>
          )}
          <ErrorText error={status.error} />
        </div>
        <div className="flex items-center justify-end gap-2">
          <ErrorText error={save.error} />
          {save.isSuccess && <span className="text-sm text-muted-foreground">Saved.</span>}
          <Button onClick={() => save.mutate(s)} disabled={save.isPending}>Save AI settings</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function TemplateEditor({ t }: { t: PromptTemplate }) {
  const qc = useQueryClient()
  const [text, setText] = useLocalCopy(t.text)
  const done = () => qc.invalidateQueries({ queryKey: ['ai-templates'] })
  const save = useMutation({ mutationFn: () => api.put(`/api/ai/templates/${t.name}`, { text }), onSuccess: done })
  const reset = useMutation({ mutationFn: () => api.post(`/api/ai/templates/${t.name}/reset`), onSuccess: done })
  const missing = t.placeholders.filter((p) => !text.includes(`{{${p}}}`))
  return (
    <div className="flex flex-col gap-2">
      <Textarea rows={16} value={text} onChange={(e) => setText(e.target.value)} className="font-mono text-xs" aria-label={`${t.name} template`} />
      <p className="text-sm text-muted-foreground">
        Placeholders: {t.placeholders.map((p) => <code key={p} className="mr-1 rounded bg-muted px-1">{`{{${p}}}`}</code>)}
        {missing.length > 0 && <span className="text-attention">Missing ones are added at the end automatically, so the rules and output format are always included.</span>}
      </p>
      <div className="flex items-center justify-end gap-2">
        <ErrorText error={save.error || reset.error} />
        {t.edited && <Button variant="outline" onClick={() => reset.mutate()} disabled={reset.isPending}><RotateCcw className="size-4" /> Reset to default</Button>}
        <Button onClick={() => save.mutate()} disabled={save.isPending || text === t.text}>Save template</Button>
      </div>
    </div>
  )
}

export function PromptTemplatesTab() {
  const q = useQuery({ queryKey: ['ai-templates'], queryFn: () => api.get<PromptTemplate[]>('/api/ai/templates') })
  const [name, setName] = useState('tailor_resume')
  const t = q.data?.find((x) => x.name === name)
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1">
          {(q.data ?? []).map((x) => (
            <Button key={x.name} size="sm" variant={x.name === name ? 'selected' : 'outline'} aria-pressed={x.name === name} onClick={() => setName(x.name)}>
              {TASK_LABEL[x.name] ?? 'Fix-up'}{x.edited && ' •'}
            </Button>
          ))}
        </div>
        <ErrorText error={q.error} />
        {t && <TemplateEditor key={t.name} t={t} />}
        <p className="text-sm text-muted-foreground">Saved as files in <code>backend/ai/templates/</code>. A dot (•) marks a template you changed.</p>
      </CardContent>
    </Card>
  )
}
