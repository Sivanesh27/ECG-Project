import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { Job } from '../types'

/** Polls GET /analysis/jobs/{id} once a second until the job completes or fails. */
export function useJob(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!jobId) return
    let stop = false
    const tick = async () => {
      try {
        const j = await api.job(jobId)
        if (stop) return
        setJob(j)
        if (j.status === 'complete' || j.status === 'error') return
      } catch (e: any) { if (!stop) { setError(e.message); return } }
      setTimeout(tick, 1000)
    }
    tick()
    return () => { stop = true }
  }, [jobId])
  return { job, error }
}
