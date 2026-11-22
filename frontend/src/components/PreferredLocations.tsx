import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { Profile, Settings } from '@/api/types'
import { Button } from '@/components/ui/button'
import { ErrorText } from './common'
import LocationPicker from './LocationPicker'

/** Edit Profile.preferred_locations (+ remote_ok via the "Remote" chip) with the state/town picker. */
export default function PreferredLocations({ onSaved, saveLabel = 'Save locations' }: { onSaved?: () => void; saveLabel?: string }) {
  const qc = useQueryClient()
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const settings = useQuery({ queryKey: ['settings'], queryFn: () => api.get<Settings>('/api/settings') })
  const [value, setValue] = useState<string[] | null>(null)
  useEffect(() => {
    if (profile.data && value === null) {
      const places = profile.data.preferred_locations.filter((p) => p.toLowerCase() !== 'remote')
      setValue(profile.data.remote_ok ? [...places, 'Remote'] : places)
    }
  }, [profile.data, value])

  const save = useMutation({
    mutationFn: () => {
      const v = value ?? []
      return api.put('/api/profile', {
        ...profile.data!,
        preferred_locations: v.filter((p) => p.toLowerCase() !== 'remote'),
        remote_ok: v.some((p) => p.toLowerCase() === 'remote'),
      })
    },
    onSuccess: () => {
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
        <Button onClick={() => save.mutate()} disabled={save.isPending}>{saveLabel}</Button>
      </div>
    </div>
  )
}
