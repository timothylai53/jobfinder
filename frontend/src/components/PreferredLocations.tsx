import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { Profile, Settings } from '@/api/types'
import { Button } from '@/components/ui/button'
import { ErrorText } from './common'
import LocationPicker from './LocationPicker'
import { useUnsavedChanges } from '@/lib/unsaved'

/** Edit Profile.preferred_locations (+ remote_ok via the "Remote" chip) with the state/town picker. */
/** The profile's places as the picker shows them: Remote is a place in the list, not a separate switch. */
function savedPlaces(p: Profile): string[] {
  const places = p.preferred_locations.filter((x) => x.toLowerCase() !== 'remote')
  return p.remote_ok ? [...places, 'Remote'] : places
}

export default function PreferredLocations({ onSaved, saveLabel = 'Save locations' }: { onSaved?: () => void; saveLabel?: string }) {
  const qc = useQueryClient()
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const settings = useQuery({ queryKey: ['settings'], queryFn: () => api.get<Settings>('/api/settings') })
  // Local edits; until the first one, the picker shows what the profile has saved.
  const [edited, setValue] = useState<string[] | null>(null)
  const value = edited ?? (profile.data ? savedPlaces(profile.data) : null)
  useUnsavedChanges(edited !== null && !!profile.data && JSON.stringify(edited) !== JSON.stringify(savedPlaces(profile.data)))

  const save = useMutation({
    mutationFn: () => {
      const v = value ?? []
      return api.put<Profile>('/api/profile', {
        ...profile.data!,
        preferred_locations: v.filter((p) => p.toLowerCase() !== 'remote'),
        remote_ok: v.some((p) => p.toLowerCase() === 'remote'),
      })
    },
    onSuccess: (saved) => {
      qc.setQueryData(['profile'], saved)
      setValue(null) // clean at once: the picker now shows the saved places
      for (const k of ['profile', 'jobs', 'job', 'dashboard']) qc.invalidateQueries({ queryKey: [k] })
      onSaved?.()
    },
  })

  if (!profile.data || !settings.data || value === null) return <ErrorText error={profile.error || settings.error} />
  return (
    <div className="flex flex-col gap-3">
      <LocationPicker value={value} onChange={setValue} locationMap={settings.data.locations} />
      <p className="text-sm text-muted-foreground">
        A whole state covers every town listed under it. Choose “Remote” if remote jobs are fine. Jobs outside these get 0 of 5 location points.
      </p>
      <div className="flex items-center justify-end gap-2">
        {save.isSuccess && <span className="text-sm text-muted-foreground">Saved. Jobs rescored.</span>}
        <ErrorText error={save.error} />
        <Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? 'Saving…' : saveLabel}</Button>
      </div>
    </div>
  )
}
