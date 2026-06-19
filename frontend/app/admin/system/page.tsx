'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';

interface SystemHealth {
  status: string;
  database: { status: string; latency_ms?: number };
  redis: { status: string; latency_ms?: number };
  r2: { status: string };
  replicate: { status: string };
  system: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    load_average?: number[];
  };
}

export default function SystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const { getToken } = useAuth();

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  async function fetchHealth() {
    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/admin/system/health`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to fetch health');

      const data = await response.json();
      setHealth(data);
    } catch (error) {
      console.error('Error fetching health:', error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-400">Loading system health...</div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400">Failed to load system health</div>
      </div>
    );
  }

  const overallHealthy = health.status === 'healthy';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">System Health</h1>
        <p className="text-zinc-400">Monitor system status and resource usage</p>
      </div>

      {/* Overall Status */}
      <div
        className={`rounded-lg p-6 border ${
          overallHealthy
            ? 'bg-green-500/10 border-green-500/50'
            : 'bg-red-500/10 border-red-500/50'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="text-3xl">{overallHealthy ? '✅' : '❌'}</div>
          <div>
            <div
              className={`text-xl font-bold ${
                overallHealthy ? 'text-green-400' : 'text-red-400'
              }`}
            >
              System {overallHealthy ? 'Healthy' : 'Degraded'}
            </div>
            <div className="text-sm text-zinc-400">
              Last checked: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>

      {/* Services Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ServiceCard
          name="Database"
          status={health.database.status}
          latency={health.database.latency_ms}
        />
        <ServiceCard
          name="Redis"
          status={health.redis.status}
          latency={health.redis.latency_ms}
        />
        <ServiceCard name="R2 Storage" status={health.r2.status} />
        <ServiceCard name="Replicate API" status={health.replicate.status} />
      </div>

      {/* System Resources */}
      <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
        <h2 className="text-xl font-bold text-white mb-4">System Resources</h2>
        <div className="space-y-4">
          <ResourceBar
            label="CPU Usage"
            value={health.system.cpu_percent}
            max={100}
            unit="%"
          />
          <ResourceBar
            label="Memory Usage"
            value={health.system.memory_percent}
            max={100}
            unit="%"
          />
          <ResourceBar
            label="Disk Usage"
            value={health.system.disk_percent}
            max={100}
            unit="%"
          />
          {health.system.load_average && (
            <div>
              <div className="text-sm text-zinc-400 mb-2">Load Average</div>
              <div className="text-white font-mono">
                {health.system.load_average.map((l) => l.toFixed(2)).join(', ')}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="bg-zinc-900 rounded-lg p-6 border border-zinc-800">
        <h2 className="text-xl font-bold text-white mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button
            onClick={fetchHealth}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            🔄 Refresh
          </button>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/metrics`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-zinc-800 text-white text-center rounded-lg hover:bg-zinc-700 transition-colors"
          >
            📊 Metrics
          </a>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/health`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-zinc-800 text-white text-center rounded-lg hover:bg-zinc-700 transition-colors"
          >
            🏥 Health API
          </a>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL}/api/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-zinc-800 text-white text-center rounded-lg hover:bg-zinc-700 transition-colors"
          >
            📚 API Docs
          </a>
        </div>
      </div>
    </div>
  );
}

function ServiceCard({
  name,
  status,
  latency,
}: {
  name: string;
  status: string;
  latency?: number;
}) {
  const isHealthy = status === 'ok' || status === 'healthy';

  return (
    <div
      className={`rounded-lg p-4 border ${
        isHealthy
          ? 'bg-green-500/10 border-green-500/50'
          : 'bg-red-500/10 border-red-500/50'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-white font-medium">{name}</div>
        <div className="text-xl">{isHealthy ? '✅' : '❌'}</div>
      </div>
      <div className={`text-sm ${isHealthy ? 'text-green-400' : 'text-red-400'}`}>
        {status}
      </div>
      {latency !== undefined && (
        <div className="text-xs text-zinc-400 mt-1">{latency}ms latency</div>
      )}
    </div>
  );
}

function ResourceBar({
  label,
  value,
  max,
  unit,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
}) {
  const percentage = (value / max) * 100;
  const color =
    percentage > 90
      ? 'bg-red-500'
      : percentage > 70
      ? 'bg-yellow-500'
      : 'bg-green-500';

  return (
    <div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-zinc-400">{label}</span>
        <span className="text-white font-mono">
          {value.toFixed(1)}
          {unit}
        </span>
      </div>
      <div className="w-full bg-zinc-800 rounded-full h-2">
        <div
          className={`${color} h-2 rounded-full transition-all duration-300`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}
