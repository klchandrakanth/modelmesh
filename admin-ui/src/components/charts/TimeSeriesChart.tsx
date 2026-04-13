import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import type { TimeseriesBucket } from '../../api/client'

interface Props {
  buckets: TimeseriesBucket[]
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit', minute: '2-digit',
  })
}

export default function TimeSeriesChart({ buckets }: Props) {
  if (buckets.length === 0) {
    return <p className="text-gray-400 text-sm">No data for this window yet — send some requests.</p>
  }

  const data = buckets.map((b) => ({
    time: fmtTime(b.ts),
    requests: b.requests,
    errors: b.errors,
    latency: b.avg_latency_ms,
  }))

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="time" tick={{ fontSize: 11 }} />
        <YAxis yAxisId="requests" orientation="left" tick={{ fontSize: 11 }} label={{ value: 'req', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }} />
        <YAxis yAxisId="latency" orientation="right" tick={{ fontSize: 11 }} label={{ value: 'ms', angle: 90, position: 'insideRight', style: { fontSize: 10 } }} />
        <Tooltip />
        <Legend />
        <Line yAxisId="requests" type="monotone" dataKey="requests" stroke="#6366f1" dot={false} strokeWidth={2} />
        <Line yAxisId="requests" type="monotone" dataKey="errors" stroke="#ef4444" dot={false} strokeWidth={2} />
        <Line yAxisId="latency" type="monotone" dataKey="latency" stroke="#f59e0b" dot={false} strokeWidth={2} name="avg latency (ms)" />
      </LineChart>
    </ResponsiveContainer>
  )
}
