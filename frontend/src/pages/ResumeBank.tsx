import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { BaseResume, ExperienceItem, ExperienceItemInput, Profile } from '@/api/types'
import { ErrorText, PageHeader } from '@/components/common'
import ItemEditor from '@/components/ItemEditor'
import ResumeUpload from '@/components/ResumeUpload'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

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

// ---------- base resumes ----------

function Resumes({ items }: { items: ExperienceItem[] }) {
  const qc = useQueryClient()
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => api.get<BaseResume[]>('/api/resumes') })
  const [newName, setNewName] = useState('')
  const update = useMutation({
    mutationFn: (r: { id: number; name: string; item_ids: number[] }) => api.put(`/api/resumes/${r.id}`, r),
    onSuccess: () => invalidateAll(qc),
  })
  const create = useMutation({
    mutationFn: () => api.post('/api/resumes', { name: newName, item_ids: [] }),
    onSuccess: () => {
      setNewName('')
      invalidateAll(qc)
    },
  })
  const del = useMutation({ mutationFn: (id: number) => api.del(`/api/resumes/${id}`), onSuccess: () => invalidateAll(qc) })
  return (
    <section aria-labelledby="base-resumes" className="flex flex-col gap-3">
      <div>
        <h2 id="base-resumes" className="text-lg font-semibold">Base resumes</h2>
        <p className="text-sm text-muted-foreground">Each one is a selection of bank items, e.g. one for software roles and one for IT support.</p>
      </div>
      <div className="flex flex-col gap-4">
        <ErrorText error={resumes.error || update.error || create.error} />
        {(resumes.data ?? []).map((r) => (
          <div key={r.id} className="border-b pb-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="font-medium">{r.name}</div>
              <Button size="sm" variant="ghost" onClick={() => confirm(`Delete BaseResume “${r.name}”? Its Experience Bank items stay.`) && del.mutate(r.id)}>
                Delete
              </Button>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {items.map((it) => (
                <label key={it.id} className="flex items-center gap-1 text-sm">
                  <input
                    type="checkbox"
                    checked={r.item_ids.includes(it.id)}
                    onChange={(e) =>
                      update.mutate({
                        id: r.id,
                        name: r.name,
                        item_ids: e.target.checked ? [...r.item_ids, it.id] : r.item_ids.filter((x) => x !== it.id),
                      })
                    }
                  />
                  <span className="font-mono text-xs">{it.code}</span> {it.title}
                </label>
              ))}
            </div>
          </div>
        ))}
        <div className="flex gap-2">
          <Input placeholder="New BaseResume name" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-64" />
          <Button variant="outline" disabled={!newName.trim()} onClick={() => create.mutate()}>Create</Button>
        </div>
      </div>
    </section>
  )
}

/** Delete every bank item and BaseResume, after an automatic database backup. */
function ClearBank({ count }: { count: number }) {
  const qc = useQueryClient()
  const clear = useMutation({
    mutationFn: () => api.post<{ backup: string; deleted_items: number; deleted_resumes: number }>('/api/experience/clear'),
    onSuccess: () => invalidateAll(qc),
  })
  const ask = () =>
    confirm(
      `Delete all ${count} Experience Bank items and all BaseResumes?\n\n` +
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
      <Resumes items={list} />
    </div>
  )
}
