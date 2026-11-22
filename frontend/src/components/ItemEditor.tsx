import type { ExperienceItemInput, ItemType } from '@/api/types'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field, ListInput, NativeSelect } from './common'

const ITEM_TYPES: ItemType[] = ['work', 'project', 'education', 'achievement', 'certification', 'publication']

/** Edit one Experience Bank item (used for both parsed drafts and saved items). */
export default function ItemEditor({ value, onChange }: { value: ExperienceItemInput; onChange: (v: ExperienceItemInput) => void }) {
  const set = <K extends keyof ExperienceItemInput>(k: K, v: ExperienceItemInput[K]) => onChange({ ...value, [k]: v })
  return (
    <div className="grid grid-cols-6 gap-2">
      <Field label="Type">
        <NativeSelect value={value.type} onChange={(v) => set('type', v as ItemType)} options={ITEM_TYPES} />
      </Field>
      <Field label="Title" className="col-span-2">
        <Input value={value.title} onChange={(e) => set('title', e.target.value)} />
      </Field>
      <Field label="Organization" className="col-span-3">
        <Input value={value.organization} onChange={(e) => set('organization', e.target.value)} />
      </Field>
      <Field label="Start">
        <Input value={value.start} placeholder="Jun 2025" onChange={(e) => set('start', e.target.value)} />
      </Field>
      <Field label="End">
        <Input value={value.end} placeholder="Present" onChange={(e) => set('end', e.target.value)} />
      </Field>
      <Field label="Skills (comma-separated)" className="col-span-4">
        <ListInput value={value.skills} onChange={(v) => set('skills', v)} />
      </Field>
      <Field label="Bullets (one per line)" className="col-span-6">
        <Textarea
          rows={Math.max(2, value.bullets.length + 1)}
          value={value.bullets.join('\n')}
          onChange={(e) => set('bullets', e.target.value.split('\n'))}
          onBlur={() => set('bullets', value.bullets.map((b) => b.trim()).filter(Boolean))}
        />
      </Field>
    </div>
  )
}
