import type { AppSettings, Analysis, Dashboard, EcgWindow, HrSeries, Job, RR, SessionRow, UploadResult, User } from '../types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

function csrf(): string {
  const m = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)
  return m ? decodeURIComponent(m[1]) : ''
}

function messageFrom(body: any, fallback: string): string {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e: any) => `${(e.loc || []).slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
  return fallback
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + url, {
    method, credentials: 'include',
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrf() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let data: any = null
  try { data = text ? JSON.parse(text) : null } catch { /* non-JSON error page */ }
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, `Request failed (${res.status})`))
  return data as T
}

export function uploadFile(file: File, onProgress: (pct: number) => void): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + '/uploads')
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', csrf())
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)) }
    xhr.onerror = () => reject(new ApiError(0, 'Network error while uploading'))
    xhr.onload = () => {
      let data: any = null
      try { data = JSON.parse(xhr.responseText) } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new ApiError(xhr.status, messageFrom(data, `Upload failed (${xhr.status})`)))
    }
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}

export const api = {
  me: () => request<User>('GET', '/auth/me'),
  login: (email: string, password: string, remember: boolean) => request<User>('POST', '/auth/login', { email, password, remember }),
  register: (b: Record<string, unknown>) => request<User>('POST', '/auth/register', b),
  logout: () => request<{ ok: boolean }>('POST', '/auth/logout'),
  forgot: (email: string) => request<{ message: string }>('POST', '/auth/forgot-password', { email }),
  reset: (token: string, password: string) => request('POST', '/auth/reset-password', { token, password }),
  deleteAccount: (password: string) => request('DELETE', '/auth/me', { password }),

  dashboard: () => request<Dashboard>('GET', '/dashboard'),
  sessions: () => request<{ items: SessionRow[]; total: number }>('GET', '/sessions?limit=200'),
  deleteSession: (id: string) => request('DELETE', `/sessions/${id}`),
  analysis: (id: string) => request<Analysis>('GET', `/analysis/${id}`),
  hr: (id: string) => request<HrSeries>('GET', `/analysis/${id}/hr`),
  rr: (id: string) => request<RR>('GET', `/analysis/${id}/rr`),
  movement: (id: string) => request<{ movement: Record<string, any>; t?: number[]; v?: number[] }>('GET', `/analysis/${id}/movement`),
  ecg: (id: string, t0?: number, t1?: number, maxPoints = 8000) => {
    const q = new URLSearchParams({ max_points: String(maxPoints) })
    if (t0 !== undefined) q.set('t0', String(t0))
    if (t1 !== undefined) q.set('t1', String(t1))
    return request<EcgWindow>('GET', `/analysis/${id}/ecg?${q}`)
  },
  reprocess: (id: string) => request<{ job_id: string }>('POST', `/analysis/${id}/reprocess`),
  process: (upload_id: string, subject: Record<string, unknown>, session_keys: string[]) =>
    request<{ job_id: string }>('POST', '/analysis/process', { upload_id, subject, session_keys }),
  job: (id: string) => request<Job>('GET', `/analysis/jobs/${id}`),
  deleteUpload: (id: string) => request('DELETE', `/uploads/${id}`),

  settings: () => request<AppSettings>('GET', '/settings'),
  saveSettings: (s: AppSettings) => request<AppSettings>('PUT', '/settings', s),
  downloadUrl: (id: string, what: 'report' | 'rr' | 'hr' | 'summary' | 'json') =>
    what === 'report' ? `${BASE}/analysis/${id}/report` : `${BASE}/analysis/${id}/export?kind=${what}`,
}
