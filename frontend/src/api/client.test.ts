import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client'

const respond = (status: number, body: string) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status, statusText: 'x' })))

afterEach(() => vi.unstubAllGlobals())

describe('api client errors', () => {
  it('keeps the status and the text of a plain-text error (500, or the local-only 403)', async () => {
    respond(500, 'Internal Server Error')
    await expect(api.get('/api/x')).rejects.toMatchObject({ status: 500, message: 'Internal Server Error' })
    respond(403, 'Cross-site request refused.')
    await expect(api.post('/api/x', {})).rejects.toBeInstanceOf(ApiError)
  })
  it('still reads FastAPI JSON errors and normal JSON replies', async () => {
    respond(409, JSON.stringify({ detail: 'Already saved' }))
    await expect(api.get('/api/x')).rejects.toMatchObject({ status: 409, message: 'Already saved' })
    respond(200, JSON.stringify({ ok: true }))
    await expect(api.get('/api/x')).resolves.toEqual({ ok: true })
  })
})
