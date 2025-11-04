import { useState, useEffect } from 'react';
import { Activity, Cpu, Thermometer, HardDrive, MemoryStick, Zap, RefreshCw, AlertTriangle } from 'lucide-react';

interface SystemMetrics {
  power_mode: {
    name: string;
    id: string;
    is_max: boolean;
  };
  cpu_frequencies: Array<{
    cpu: number;
    freq_ghz: number;
    type: string;
  }>;
  cpu_avg: {
    performance: number;
    efficiency: number;
  };
  temperature: {
    max_c: number;
    zones: number[];
    warning: boolean;
    critical: boolean;
  };
  cpu_usage: {
    overall: number;
  };
  memory: {
    total_gb: number;
    used_gb: number;
    percent: number;
    available_gb: number;
  };
  storage: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent: number;
  };
}

export function Health() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/api/v1/system-metrics');
      const data = await response.json();
      setMetrics(data);
    } catch (error) {
      console.error('Failed to fetch system metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchMetrics();
    }, 2000); // Refresh every 2 seconds

    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (loading || !metrics) {
    return (
      <div className="p-4 lg:p-8 flex items-center justify-center">
        <div className="text-gray-500">Loading system metrics...</div>
      </div>
    );
  }

  const MetricCard = ({
    title,
    icon: Icon,
    children,
    warning = false,
    critical = false
  }: {
    title: string;
    icon: any;
    children: React.ReactNode;
    warning?: boolean;
    critical?: boolean;
  }) => (
    <div className={`bg-white rounded-lg shadow-lg p-6 ${critical ? 'border-2 border-red-500' : warning ? 'border-2 border-yellow-500' : ''}`}>
      <div className="flex items-center gap-3 mb-4">
        <Icon className={`w-6 h-6 ${critical ? 'text-red-600' : warning ? 'text-yellow-600' : 'text-blue-600'}`} />
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      {children}
    </div>
  );

  const ProgressBar = ({
    percent,
    warning = false,
    critical = false
  }: {
    percent: number;
    warning?: boolean;
    critical?: boolean;
  }) => (
    <div className="w-full bg-gray-200 rounded-full h-3">
      <div
        className={`h-3 rounded-full transition-all ${
          critical ? 'bg-red-600' : warning ? 'bg-yellow-500' : 'bg-blue-600'
        }`}
        style={{ width: `${Math.min(100, percent)}%` }}
      />
    </div>
  );

  return (
    <div className="p-4 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl lg:text-3xl font-bold text-gray-900">System Health</h1>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh
            </label>
            <button
              onClick={() => fetchMetrics()}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Alerts */}
        {(metrics.power_mode.is_max === false || metrics.temperature.warning || metrics.temperature.critical) && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-yellow-900">
                <p className="font-medium mb-1">System Warnings:</p>
                <ul className="space-y-1">
                  {!metrics.power_mode.is_max && (
                    <li>Power mode is not set to MAXN_SUPER (Mode 2). Recording performance may be degraded.</li>
                  )}
                  {metrics.temperature.warning && !metrics.temperature.critical && (
                    <li>Temperature is elevated ({metrics.temperature.max_c}°C). Consider improving cooling.</li>
                  )}
                  {metrics.temperature.critical && (
                    <li className="text-red-600 font-bold">Critical temperature ({metrics.temperature.max_c}°C)! System may throttle or shut down.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Power Mode */}
          <MetricCard
            title="Power Mode"
            icon={Zap}
            warning={!metrics.power_mode.is_max}
          >
            <div className="space-y-2">
              <div className="text-3xl font-bold text-gray-900">{metrics.power_mode.name}</div>
              <div className="text-sm text-gray-600">Mode ID: {metrics.power_mode.id}</div>
              {!metrics.power_mode.is_max && (
                <div className="text-sm text-yellow-600 font-medium">
                  ⚠ Not in MAXN mode
                </div>
              )}
              {metrics.power_mode.is_max && (
                <div className="text-sm text-green-600 font-medium">
                  ✓ Optimal mode
                </div>
              )}
            </div>
          </MetricCard>

          {/* CPU Frequencies */}
          <MetricCard title="CPU Frequencies" icon={Cpu}>
            <div className="space-y-3">
              <div>
                <div className="text-sm text-gray-600 mb-1">Performance Cores (0-3)</div>
                <div className="text-2xl font-bold text-gray-900">{metrics.cpu_avg.performance} GHz</div>
                <div className="text-xs text-gray-500">Target: 1.728 GHz</div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Efficiency Cores (4-5)</div>
                <div className="text-2xl font-bold text-gray-900">{metrics.cpu_avg.efficiency} GHz</div>
                <div className="text-xs text-gray-500">Target: 0.729 GHz</div>
              </div>
            </div>
          </MetricCard>

          {/* Temperature */}
          <MetricCard
            title="Temperature"
            icon={Thermometer}
            warning={metrics.temperature.warning}
            critical={metrics.temperature.critical}
          >
            <div className="space-y-2">
              <div className="text-3xl font-bold text-gray-900">{metrics.temperature.max_c}°C</div>
              <div className="text-sm text-gray-600">Max across all zones</div>
              <ProgressBar
                percent={(metrics.temperature.max_c / 100) * 100}
                warning={metrics.temperature.warning}
                critical={metrics.temperature.critical}
              />
              <div className="text-xs text-gray-500">
                Safe: &lt;75°C | Warning: 75-85°C | Critical: &gt;85°C
              </div>
            </div>
          </MetricCard>

          {/* CPU Usage */}
          <MetricCard title="CPU Usage" icon={Activity}>
            <div className="space-y-2">
              <div className="text-3xl font-bold text-gray-900">{metrics.cpu_usage.overall}%</div>
              <div className="text-sm text-gray-600">Overall system usage</div>
              <ProgressBar
                percent={metrics.cpu_usage.overall}
                warning={metrics.cpu_usage.overall > 80}
                critical={metrics.cpu_usage.overall > 95}
              />
            </div>
          </MetricCard>

          {/* Memory */}
          <MetricCard title="Memory" icon={MemoryStick}>
            <div className="space-y-2">
              <div className="text-2xl font-bold text-gray-900">
                {metrics.memory.used_gb} / {metrics.memory.total_gb} GB
              </div>
              <div className="text-sm text-gray-600">{metrics.memory.percent}% used</div>
              <ProgressBar
                percent={metrics.memory.percent}
                warning={metrics.memory.percent > 80}
                critical={metrics.memory.percent > 95}
              />
              <div className="text-xs text-gray-500">
                Available: {metrics.memory.available_gb} GB
              </div>
            </div>
          </MetricCard>

          {/* Storage */}
          <MetricCard title="Storage (/mnt/recordings)" icon={HardDrive}>
            <div className="space-y-2">
              <div className="text-2xl font-bold text-gray-900">
                {metrics.storage.free_gb} GB free
              </div>
              <div className="text-sm text-gray-600">{metrics.storage.percent}% used</div>
              <ProgressBar
                percent={metrics.storage.percent}
                warning={metrics.storage.percent > 80}
                critical={metrics.storage.percent > 90}
              />
              <div className="text-xs text-gray-500">
                {metrics.storage.used_gb} / {metrics.storage.total_gb} GB used
              </div>
            </div>
          </MetricCard>
        </div>

        {/* Detailed CPU Info */}
        <div className="mt-6 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">CPU Core Details</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {metrics.cpu_frequencies.map((cpu) => (
              <div key={cpu.cpu} className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-xs text-gray-600 mb-1">
                  CPU {cpu.cpu} ({cpu.type === 'performance' ? 'Perf' : 'Eff'})
                </div>
                <div className="text-lg font-bold text-gray-900">{cpu.freq_ghz} GHz</div>
              </div>
            ))}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="text-sm text-blue-900">
            <p className="font-medium mb-2">About Jetson Orin Nano Super</p>
            <ul className="space-y-1 text-blue-800">
              <li><strong>6 Cores:</strong> 4 performance cores (1.728 GHz) + 2 efficiency cores (729 MHz)</li>
              <li><strong>Power Mode 2 (MAXN_SUPER)</strong> required for reliable 30fps dual-camera recording</li>
              <li><strong>Each camera uses ~2.01 CPU cores</strong> during recording</li>
              <li><strong>System auto-enforces</strong> Mode 2 every 5 minutes via health monitor</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
