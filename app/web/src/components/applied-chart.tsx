/* Applications sent per week, last 8 weeks. One series, so one colour (--chart-1, validated in both themes). */
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'
import type { Summary } from '@/lib/api'
import { day } from '@/lib/format'

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer])

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export function AppliedChart({ weeks }: { weeks: Summary['applied_by_week'] }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'svg' })
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const draw = () => {
      const ink = cssVar('--muted-foreground')
      const line = cssVar('--border')
      chart.setOption({
        animation: !reduce,
        animationDuration: 500,
        grid: { left: 4, right: 4, top: 12, bottom: 4, containLabel: true },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow', shadowStyle: { color: cssVar('--foreground'), opacity: 0.04 } },
          backgroundColor: cssVar('--popover'),
          borderColor: line,
          textStyle: { color: cssVar('--popover-foreground'), fontSize: 12, fontFamily: 'Geist Variable' },
          formatter: (p: { name: string; value: number }[]) => `Week of ${p[0].name}<br/><b>${p[0].value}</b> applied`,
        },
        xAxis: {
          type: 'category',
          data: weeks.map((w) => day(w.week)),
          axisLine: { lineStyle: { color: line } },
          axisTick: { show: false },
          axisLabel: { color: ink, fontSize: 11, fontFamily: 'Geist Variable', hideOverlap: true },
        },
        yAxis: {
          type: 'value',
          minInterval: 1,
          axisLabel: { color: ink, fontSize: 11, fontFamily: 'Geist Mono Variable' },
          splitLine: { lineStyle: { color: line, type: 'dashed' } },
        },
        series: [{
          type: 'bar',
          barMaxWidth: 28,
          itemStyle: { color: cssVar('--chart-1'), borderRadius: [5, 5, 0, 0] },
          emphasis: { itemStyle: { color: cssVar('--chart-1'), opacity: 0.85 } },
          data: weeks.map((w) => w.count),
        }],
      }, true)
    }
    draw()
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)
    // A theme switch toggles the class on <html>: restyle from the new CSS variables.
    const mo = new MutationObserver(draw)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => {
      ro.disconnect()
      mo.disconnect()
      chart.dispose()
    }
  }, [weeks])

  const total = weeks.reduce((s, w) => s + w.count, 0)
  if (total === 0) {
    return (
      <div className="grid h-48 place-items-center rounded-2xl bg-foreground/[0.03] px-6 text-center text-sm text-muted-foreground">
        No applications marked as sent in the last 8 weeks. Bars appear here once you mark some applied.
      </div>
    )
  }
  return (
    <div ref={ref} className="h-48 w-full" role="img"
      aria-label={`Applications sent per week: ${weeks.map((w) => `week of ${day(w.week)}, ${w.count}`).join('; ')}`} />
  )
}
