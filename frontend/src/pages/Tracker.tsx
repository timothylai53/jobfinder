import { DndContext, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import { STATUSES, type ApplicationRow, type Status } from '@/api/types'
import { ErrorText, NativeSelect, PageHeader, ScoreBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate } from '@/lib/score'
import { cn } from '@/lib/utils'

function useApplications() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['applications'], queryFn: () => api.get<ApplicationRow[]>('/api/applications') })
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: Status }) => api.patch(`/api/applications/${id}`, { status }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ['applications'] })
      const prev = qc.getQueryData<ApplicationRow[]>(['applications'])
      qc.setQueryData<ApplicationRow[]>(['applications'], (old) => old?.map((a) => (a.id === id ? { ...a, status } : a)))
      return { prev }
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(['applications'], ctx.prev),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['job'] })
    },
  })
  return { list, move }
}

const isOverdue = (a: ApplicationRow) => a.status === 'Applied' && !!a.follow_up_at && a.follow_up_at <= new Date().toISOString().slice(0, 10)

function Card({ app }: { app: ApplicationRow }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: app.id })
  const style = transform ? { transform: `translate(${transform.x}px, ${transform.y}px)` } : undefined
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={cn('cursor-grab rounded-md border bg-background p-2 text-sm shadow-xs', isDragging && 'z-10 opacity-80 shadow-md')}
    >
      <div className="flex items-start justify-between gap-2">
        <Link to={`/jobs/${app.job_id}`} className="font-medium hover:underline" onPointerDown={(e) => e.stopPropagation()}>
          {app.job_title}
        </Link>
        <ScoreBadge score={app.score} />
      </div>
      <div className="text-xs text-muted-foreground">{app.company}</div>
      {app.applied_at && <div className="text-xs text-muted-foreground">Applied {formatDate(app.applied_at)}</div>}
      {app.follow_up_at && app.status === 'Applied' && (
        <div className={cn('text-xs', isOverdue(app) ? 'font-medium text-red-600' : 'text-muted-foreground')}>
          Follow up {formatDate(app.follow_up_at)}
        </div>
      )}
    </div>
  )
}

function Column({ status, apps }: { status: Status; apps: ApplicationRow[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <div ref={setNodeRef} className={cn('flex min-h-64 w-60 shrink-0 flex-col gap-2 rounded-lg bg-muted/60 p-2', isOver && 'ring-2 ring-ring')}>
      <div className="flex justify-between px-1 text-sm font-medium">
        {status}
        <span className="text-muted-foreground">{apps.length}</span>
      </div>
      {apps.map((a) => (
        <Card key={a.id} app={a} />
      ))}
    </div>
  )
}

function Kanban({ apps, onMove }: { apps: ApplicationRow[]; onMove: (id: number, s: Status) => void }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))
  const onDragEnd = (e: DragEndEvent) => {
    const target = e.over?.id as Status | undefined
    const app = apps.find((a) => a.id === e.active.id)
    if (app && target && target !== app.status) onMove(app.id, target)
  }
  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {STATUSES.map((s) => (
          <Column key={s} status={s} apps={apps.filter((a) => a.status === s)} />
        ))}
      </div>
    </DndContext>
  )
}

type Col = 'job_title' | 'company' | 'status' | 'score' | 'applied_at' | 'follow_up_at' | 'updated_at'

function AppTable({ apps, onMove }: { apps: ApplicationRow[]; onMove: (id: number, s: Status) => void }) {
  const [sort, setSort] = useState<Col>('updated_at')
  const [desc, setDesc] = useState(true)
  const [status, setStatus] = useState('All')
  const [q, setQ] = useState('')
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const f = apps.filter(
      (a) => (status === 'All' || a.status === status) && (!needle || `${a.job_title} ${a.company} ${a.notes}`.toLowerCase().includes(needle)),
    )
    return f.sort((a, b) => {
      const av = a[sort] ?? ''
      const bv = b[sort] ?? ''
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
      return desc ? -cmp : cmp
    })
  }, [apps, sort, desc, status, q])
  const head = (c: Col, label: string) => (
    <TableHead>
      <button
        className="hover:underline"
        onClick={() => {
          if (sort === c) setDesc(!desc)
          else {
            setSort(c)
            setDesc(false)
          }
        }}
      >
        {label} {sort === c ? (desc ? '↓' : '↑') : ''}
      </button>
    </TableHead>
  )
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <NativeSelect value={status} onChange={setStatus} options={['All', ...STATUSES]} />
        <Input className="w-64" placeholder="Search title, company, notes" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="rounded-lg border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              {head('job_title', 'Job')}
              {head('company', 'Company')}
              {head('status', 'Status')}
              {head('score', 'Score')}
              {head('applied_at', 'Applied')}
              {head('follow_up_at', 'Follow up')}
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Link to={`/jobs/${a.job_id}`} className="font-medium hover:underline">
                    {a.job_title}
                  </Link>
                </TableCell>
                <TableCell>{a.company}</TableCell>
                <TableCell>
                  <NativeSelect value={a.status} onChange={(v) => onMove(a.id, v as Status)} options={[...STATUSES]} />
                </TableCell>
                <TableCell>
                  <ScoreBadge score={a.score} />
                </TableCell>
                <TableCell>{formatDate(a.applied_at)}</TableCell>
                <TableCell className={cn(isOverdue(a) && 'font-medium text-red-600')}>{formatDate(a.follow_up_at)}</TableCell>
                <TableCell className="max-w-64 truncate" title={a.notes}>
                  {a.notes}
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                  No applications. Save a job from the Jobs page.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export default function Tracker() {
  const { list, move } = useApplications()
  const [view, setView] = useState<'kanban' | 'table'>(() => (localStorage.getItem('trackerView') as 'kanban' | 'table') || 'kanban')
  const setV = (v: 'kanban' | 'table') => {
    setView(v)
    localStorage.setItem('trackerView', v)
  }
  const onMove = (id: number, status: Status) => move.mutate({ id, status })
  const apps = list.data ?? []
  return (
    <div>
      <PageHeader title="Tracker">
        <Button variant={view === 'kanban' ? 'default' : 'outline'} onClick={() => setV('kanban')}>
          Kanban
        </Button>
        <Button variant={view === 'table' ? 'default' : 'outline'} onClick={() => setV('table')}>
          Table
        </Button>
      </PageHeader>
      <ErrorText error={list.error || move.error} />
      {view === 'kanban' ? <Kanban apps={apps} onMove={onMove} /> : <AppTable apps={apps} onMove={onMove} />}
    </div>
  )
}
