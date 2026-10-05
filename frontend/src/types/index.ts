export interface User { id: string; name: string; email: string; organization?: string; role?: string }
export type Quality = 'GOOD' | 'ACCEPTABLE' | 'POOR' | 'UNKNOWN' | null | undefined

export interface Availability { ecg: boolean; hr: boolean; corrected_hr: boolean; hr_quality: boolean; movement: boolean; summary: boolean }
export interface DetectedSession {
  key: string; name: string; subject_hint?: string; start?: string; end?: string; duration_s?: number
  availability: Availability; ecg_fs_hz?: number; fs_source?: string; ecg_samples: number
  missing_samples: number; duplicate_samples: number; gaps: { gap_s: number }[]; n_chunks?: number; warnings: string[]
}
export interface UploadResult { id: string; filename: string; size: number; sessions: DetectedSession[]; summary: Record<string, number> }

export interface SessionRow {
  id: string; name: string; subjectId: string; subject: string; start?: string; end?: string; durationS?: number
  quality: Quality; availability: Availability; createdAt: string
  summary: { avg_hr?: number; max_hr?: number; min_hr?: number; rmssd?: number; pnn50?: number; training_load_source?: number; training_load_calc?: number; movement_load?: number }
}
export interface Dashboard { total_sessions: number; recent: SessionRow[]; latest?: SessionRow; average_hr_recent?: number | null; kpis: Record<string, any> }

export interface Job { job_id: string; status: 'queued' | 'processing' | 'complete' | 'error'; step: string; stepIndex: number; steps: string[]; progress: number; sessionIds: string[]; error?: string | null }

export interface Subject { name: string; age: number; gender: string; height_cm?: number; weight_kg?: number; bmi?: number; bmi_category?: string; resting_hr?: number; max_hr?: number; notes?: string }
export interface Warning { code: string; level: 'info' | 'warn' | 'error'; message: string }
export interface Zone { zone: number; label: string; lo_pct: number; hi_pct: number; lo_bpm: number; hi_bpm: number; seconds: number; percent: number; avg_hr: number | null; peak_hr: number | null }

// Nested analysis blocks are intentionally loose: the backend (analysis/pipeline.py) is the source of truth.
export interface Analysis {
  session: Record<string, any>; subject: Subject & Record<string, any>
  analysis: { warnings: Warning[]; recording: Record<string, any>; quality: Record<string, any>; hr_calc: Record<string, any>; source_vs_calculated: Record<string, any>; parameters: Record<string, any>; ecg_processing?: Record<string, any> }
  hrv: { time?: Record<string, any>; frequency?: Record<string, any>; nonlinear?: Record<string, any> }
  training_results: { training?: Record<string, any>; zones?: { zones: Zone[]; total_s: number } | null; source_zone_durations_s?: Record<string, number | null> | null }
  movement_results: { movement?: Record<string, any> }
  hr_series_stats: Record<string, any>
  interpretation: { metric: string; value: string; text: string; level: string }[]
  metric_metadata: Record<string, any>
}
export interface HrSeries { t?: number[]; v?: number[]; acc_t?: number[]; acc_v?: number[]; stats?: Record<string, any>; zones?: { zones: Zone[] } | null; hr_calc?: Record<string, any> }
export interface RR { n?: number; t_s?: number[]; rr_ms?: (number | null)[]; hr_bpm?: number[]; segment?: number[]; artifact?: boolean[]; reason?: string[]; rr_corrected_ms?: (number | null)[]; status?: string[] }
export interface EcgWindow { t: number[]; y: number[]; peaks_t: number[]; peaks_y: number[]; t_min: number; t_max: number; n_total: number; n_window: number; downsampled: boolean; segments: { segment: number; start: number; end: number }[] }

export interface AppSettings {
  hrmax_formula: '220-age' | '208-0.7age' | 'custom'; hrmax_custom?: number | null; zones: number[][]
  filter: Record<string, any>; artifact: Record<string, any>; freq: Record<string, any>; sampling_rate_override?: number | null; powerline_hz: 50 | 60
}
