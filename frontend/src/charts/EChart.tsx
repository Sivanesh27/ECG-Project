import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export type Option = echarts.EChartsOption

export function EChart({ option, height = 280, label }: { option: Option; height?: number; label: string }) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    if (!el.current) return
    chart.current = echarts.init(el.current, undefined, { renderer: 'canvas' })
    const ro = new ResizeObserver(() => chart.current?.resize())
    ro.observe(el.current)
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null }
  }, [])
  useEffect(() => { chart.current?.setOption(option, { notMerge: true }) }, [option])
  return <div ref={el} role="img" aria-label={label} style={{ height, width: '100%' }} />
}
