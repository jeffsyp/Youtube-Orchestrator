import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useStatus, useSchedules, useCancelRun } from '../hooks/useApi';

export default function Dashboard() {
  const { data, isLoading, error } = useStatus();
  const { data: schedules } = useSchedules();
  const cancelMutation = useCancelRun();

  if (isLoading) return <LoadingSkeleton />;

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 text-lg">Failed to connect to API</p>
        <p className="text-gray-500 text-sm mt-2">Make sure the backend is running at localhost:8000</p>
      </div>
    );
  }

  if (!data) return null;

  const channelCards = data.channel_stats.map((ch) => {
    const sched = schedules?.find((s) => s.channel_id === ch.id);
    return {
      ...ch,
      queue_depth: sched?.queue_depth || 0,
      paused: sched?.paused ?? true,
    };
  });

  const activeChannels = channelCards.filter((c) => !c.paused);
  const pausedChannels = channelCards.filter((c) => c.paused);

  const today = data.today_stats;
  const readyCount = data.recent_runs.filter(r => r.status === 'pending_review').length;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Content Factory</h1>
        <WorkerStatus />
      </div>

      {/* Today's stats */}
      {today && today.total > 0 && (
        <section>
          <h2 className="text-sm font-medium text-white uppercase tracking-wider mb-3">Today</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard label="Published" value={today.published} color="text-purple-400" />
            <StatCard label="Ready" value={today.ready} color="text-green-400" />
            <StatCard label="Generating" value={today.generating} color="text-yellow-400" />
            <StatCard label="Failed" value={today.failed} color="text-red-400" />
          </div>

          {today.uploads.length > 0 && (
            <div className="space-y-1.5 mb-4">
              {today.uploads.map((u, i) => (
                <div key={i} className="flex items-center gap-2 p-2 rounded bg-[#1a1a1a] border border-[#2a2a2a]">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-purple-500/15 text-purple-400">uploaded</span>
                  <span className="text-gray-500 text-xs">{u.channel}</span>
                  <span className="text-gray-200 text-sm truncate flex-1">{u.title || 'Untitled'}</span>
                  {u.publish_at && (
                    <span className="text-gray-600 text-[10px] shrink-0">
                      publishes {new Date(u.publish_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                  {u.url && (
                    <a href={u.url} target="_blank" rel="noopener noreferrer"
                      className="text-red-400 hover:text-red-300 text-xs no-underline shrink-0" onClick={e => e.stopPropagation()}>
                      YT
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {today.by_channel.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-[#2a2a2a]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[#111] text-gray-500">
                    <td className="px-3 py-2 font-medium">Channel</td>
                    <td className="px-3 py-2 text-center font-medium">Uploaded</td>
                    <td className="px-3 py-2 text-center font-medium">Ready</td>
                    <td className="px-3 py-2 text-center font-medium">Failed</td>
                    <td className="px-3 py-2 text-center font-medium">Total</td>
                  </tr>
                </thead>
                <tbody>
                  {today.by_channel.map((ch) => (
                    <tr key={ch.id} className="border-t border-[#1a1a1a] hover:bg-[#1a1a1a] transition-colors">
                      <td className="px-3 py-2">
                        <Link to={`/channels/${ch.id}`} className="text-gray-200 no-underline hover:text-white">{ch.name}</Link>
                      </td>
                      <td className={`px-3 py-2 text-center ${ch.published > 0 ? 'text-purple-400' : 'text-gray-700'}`}>{ch.published}</td>
                      <td className={`px-3 py-2 text-center ${ch.ready > 0 ? 'text-green-400' : 'text-gray-700'}`}>{ch.ready}</td>
                      <td className={`px-3 py-2 text-center ${ch.failed > 0 ? 'text-red-400' : 'text-gray-700'}`}>{ch.failed}</td>
                      <td className="px-3 py-2 text-center text-gray-500">{ch.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Running */}
      {data.running_pipelines.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-yellow-400 uppercase tracking-wider mb-3">
            Generating ({data.running_pipelines.length})
          </h2>
          <div className="space-y-2">
            {data.running_pipelines.map((run) => (
              <div key={run.id}
                className="flex items-center justify-between p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
                <Link to={`/runs/${run.id}`} className="flex items-center gap-3 flex-1 no-underline hover:opacity-80">
                  <span className="text-gray-600 text-xs font-mono">#{run.id}</span>
                  <span className="text-gray-400 text-xs">{run.channel_name}</span>
                  <span className="text-yellow-400 text-sm">{run.title || 'Generating...'}</span>
                </Link>
                <div className="flex items-center gap-3">
                  <span className="text-yellow-400 text-xs font-mono">{run.current_step}</span>
                  <button
                    onClick={() => cancelMutation.mutate(run.id)}
                    className="px-2 py-1 rounded bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-400 text-xs transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Ready for review */}
      {readyCount > 0 && (
        <section>
          <h2 className="text-sm font-medium text-green-400 uppercase tracking-wider mb-3">
            Ready ({readyCount})
          </h2>
          <div className="space-y-2">
            {data.recent_runs.filter(r => r.status === 'pending_review').map((run) => (
              <Link key={run.id} to={`/runs/${run.id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-green-500/5 border border-green-500/20 hover:border-green-500/40 transition-colors no-underline">
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-xs font-mono">#{run.id}</span>
                  <span className="text-gray-400 text-xs">{run.channel_name}</span>
                  <span className="text-green-400 text-sm">{run.title || 'Untitled'}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Channels */}
      {activeChannels.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Channels</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeChannels.map((ch) => <ChannelCard key={ch.id} channel={ch} />)}
          </div>
        </section>
      )}

      {pausedChannels.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-600 uppercase tracking-wider mb-3">
            Paused ({pausedChannels.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {pausedChannels.map((ch) => (
              <Link key={ch.id} to={`/channels/${ch.id}`}
                className="p-3 rounded-lg bg-[#111] border border-[#1a1a1a] no-underline block">
                <span className="text-gray-500 text-sm">{ch.name}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

interface ChannelCardData {
  id: number; name: string; niche: string;
  queue_depth: number; paused: boolean;
  stats: { total: number; published: number; completed: number; failed: number };
}

function ChannelCard({ channel }: { channel: ChannelCardData }) {
  const ready = channel.stats.completed;  // pending_review count
  const published = channel.stats.published;
  const total = channel.stats.total;

  return (
    <Link to={`/channels/${channel.id}`}
      className="p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] hover:border-[#3a3a3a] transition-colors no-underline block">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-white font-medium text-sm truncate">{channel.name}</h3>
        {channel.queue_depth > 0 && (
          <span className="text-blue-400 text-xs font-mono">{channel.queue_depth} queued</span>
        )}
      </div>
      <p className="text-gray-500 text-xs mb-3 truncate">{channel.niche}</p>
      {total > 0 ? (
        <div className="flex items-center gap-3 text-xs">
          {ready > 0 && <span className="text-green-400">{ready} ready</span>}
          {published > 0 && <span className="text-purple-400">{published} published</span>}
          <span className="text-gray-500">{total} total (48h)</span>
        </div>
      ) : (
        <p className="text-gray-600 text-xs">No activity</p>
      )}
    </Link>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="p-3 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <div className={`text-2xl font-bold ${value > 0 ? color : 'text-gray-600'}`}>{value}</div>
      <div className="text-gray-500 text-xs mt-1">{label}</div>
    </div>
  );
}

function WorkerStatus() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<{
    status: string; pid: number | null; started_at: number | null; uptime_seconds: number;
  }>({
    queryKey: ['worker-status'],
    queryFn: () => fetch('/api/worker/status').then(r => r.json()),
    refetchInterval: 10000,
  });

  const formatUptime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const handleToggle = async () => {
    const endpoint = data?.status === 'running' ? '/api/worker/stop' : '/api/worker/start';
    try {
      const res = await fetch(endpoint, { method: 'POST' });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['worker-status'] }), 2000);
    } catch (err) {
      alert(`Failed to toggle worker: ${err instanceof Error ? err.message : err}`);
    }
  };

  if (isLoading) return null;

  const running = data?.status === 'running';

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${running ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
        <span className="text-xs text-gray-400">
          Worker {running ? `running ${formatUptime(data?.uptime_seconds || 0)}` : 'stopped'}
        </span>
      </div>
      <button
        onClick={handleToggle}
        className={`px-3 py-1 rounded text-xs font-medium border-none cursor-pointer transition-colors ${
          running
            ? 'bg-red-500/15 text-red-400 hover:bg-red-500/30'
            : 'bg-green-500/15 text-green-400 hover:bg-green-500/30'
        }`}
      >
        {running ? 'Stop' : 'Start'}
      </button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div><div className="h-8 w-48 bg-[#1a1a1a] rounded" /></div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => <div key={i} className="h-28 bg-[#1a1a1a] rounded-lg" />)}
      </div>
    </div>
  );
}
