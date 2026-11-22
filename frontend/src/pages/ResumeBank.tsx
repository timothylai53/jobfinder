import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { ExperienceItem, ExperienceItemInput, Profile } from '@/api/types'
import { ErrorText, PageHeader } from '@/components/common'
import BaseResumes from '@/components/BaseResumes'
import ItemEditor from '@/components/ItemEditor'
import ResumeUpload from '@/components/ResumeUpload'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  for (const k of ['experience', 'resumes', 'profile', 'jobs', 'job', 'dashboard']) qc.invalidateQueries({ queryKey: [k] })
}

// ---------- bank ----------

function BankItem({ item }: { item: ExperienceItem }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState<ExperienceItemInput>(item)
  const save = useMutation({
    mutationFn: () => api.put(`/api/experience/${item.id}`, val),
    onSuccess: () => {
      setEditing(false)
      invalidateAll(qc)
    },
  })
  const del = useMutation({ mutationFn: () => api.del(`/api/experience/${item.id}`), onSuccess: () => invalidateAll(qc) })
  return (
    <li className="px-4 py-3">
      {editing ? (
        <div className="flex flex-col gap-2">
          <ItemEditor value={val} onChange={setVal} />
          <div className="flex justify-end gap-2">
            <ErrorText error={save.error} />
            <Button variant="ghost" onClick={() => { setVal(item); setEditing(false) }}>
              Cancel
            </Button>
            <Button onClick={() => save.mutate()}>Save</Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-3">
          <Badge variant="outline" className="h-6 font-mono">{item.code}</Badge>
          <div className="min-w-0 flex-1 text-sm">
            <div className="font-medium">
              {item.title} {item.organization && <span className="font-normal text-muted-foreground">· {item.organization}</span>}
            </div>
            <div className="text-xs text-muted-foreground">
              {item.type} {(item.start || item.end) && `· ${item.start}${item.start && item.end ? ' – ' : ''}${item.end}`}
            </div>
            <ul className="mt-1 list-disc pl-5">
              {item.bullets.map((b, i) => <li key={i}>{b}</li>)}
            </ul>
            {item.skills.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {item.skills.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)}
              </div>
            )}
          </div>
          <div className="flex shrink-0 flex-col gap-1">
            <Button size="sm" variant="outline" onClick={() => { setVal(item); setEditing(true) }}>Edit</Button>
            <Button size="sm" variant="ghost" onClick={() => confirm(`Delete ${item.code}? Its ID will not be reused.`) && del.mutate()}>
              Delete
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}

function NewItem({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [val, setVal] = useState<ExperienceItemInput>({ type: 'project', title: '', organization: '', start: '', end: '', bullets: [], skills: [] })
  const save = useMutation({
    mutationFn: () => api.post('/api/experience', val),
    onSuccess: () => {
      invalidateAll(qc)
      onClose()
    },
  })
  return (
    <div className="rounded-md border bg-background p-3">
      <ItemEditor value={val} onChange={setVal} />
      <div className="mt-2 flex justify-end gap-2">
        <ErrorText error={save.error} />
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button disabled={!val.title.trim()} onClick={() => save.mutate()}>Add to bank</Button>
      </div>
    </div>
  )
}

/** Delete every bank item and base resume, after an automatic database backup. */
function ClearBank({ count }: { count: number }) {
  const qc = useQueryClient()
  const clear = useMutation({
    mutationFn: () => api.post<{ backup: string; deleted_items: number; deleted_resumes: number }>('/api/experience/clear'),
    onSuccess: () => invalidateAll(qc),
  })
  const ask = () =>
    confirm(
      `Delete all ${count} Experience Bank items and all base resumes?\n\n` +
        'A backup of your database is saved to data/backups first. Your profile and skill dictionary are kept.',
    )
  return (
    <div className="flex items-center gap-2">
      {clear.data && <span className="text-sm text-muted-foreground">Cleared. Backup saved as {clear.data.backup}.</span>}
      <ErrorText error={clear.error} />
      {count > 0 && (
        <Button variant="ghost" size="sm" className="text-danger hover:bg-danger-bg hover:text-danger" disabled={clear.isPending} onClick={() => ask() && clear.mutate()}>
          Clear bank…
        </Button>
      )}
    </div>
  )
}

export default function ResumeBank() {
  const items = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const [adding, setAdding] = useState(false)
  const list = items.data ?? []
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Resume" lead="Your Experience Bank: the only facts that scores and AI-written resumes may use." />
      <ResumeUpload />
      <section aria-labelledby="bank" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="bank" className="text-lg font-semibold">Experience Bank <span className="font-normal text-muted-foreground">({list.length} items)</span></h2>
            {profile.data && profile.data.skills.length > 0 && (
              <p className="text-sm text-muted-foreground">Profile skills: {profile.data.skills.join(', ')} (edit in Settings → Profile)</p>
            )}
          </div>
          <ClearBank count={list.length} />
        </div>
        <ErrorText error={items.error} />
        {list.length > 0 && <ul className="divide-y rounded-lg border bg-background">{list.map((it) => <BankItem key={it.id} item={it} />)}</ul>}
        {adding ? <NewItem onClose={() => setAdding(false)} /> : (
          <Button variant="outline" className="self-start" onClick={() => setAdding(true)}>Add item</Button>
        )}
      </section>
      <BaseResumes items={list} />
    </div>
  )
}
