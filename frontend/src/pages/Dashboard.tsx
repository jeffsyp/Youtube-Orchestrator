import { Link } from 'react-router-dom';
import { useStatus } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';

export default function Dashboard() {
  const { data, isLoading, error } = useStatus();

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 text-lg">Failed to connect to API</p>
        <p className="text-gray-500 text-sm mt-2">
          Make sure the backend is running at localhost:8000
        </p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Pipeline overview and system health</p>
      </div>

      {/* System Health */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          System Health
        </h2>
        <div className="flex flex-wrap gap-3">
          {data.system_checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  check.active ? 'bg-green-400' : 'bg-red-400'
                }`}
              />
              <span className="text-sm text-gray-300">{check.name}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Running Pipelines */}
      {data.running_pipelines.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Running Pipelines
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.running_pipelines.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="block p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] hover:border-purple-500/50 transition-colors no-underline"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-white font-medium text-sm">
                      {run.channel_name}
                    </p>
                    <p className="text-gray-500 text-xs font-mono">
                      #{run.id}
                    </p>
                  </div>
                  <StatusBadge status={run.status} />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">Step:</span>
                    <span className="text-xs text-yellow-400 font-mono">
                      {run.current_step || 'initializing'}
                    </span>
                  </div>
                  {run.elapsed_seconds != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Elapsed:</span>
                      <span className="text-xs text-gray-300 font-mono">
                        {formatElapsed(run.elapsed_seconds)}
                      </span>
                    </div>
                  )}
                  <div className="w-full h-1 rounded-full bg-[#2a2a2a] overflow-hidden">
                    <div className="h-full bg-yellow-400 rounded-full animate-pulse w-2/3" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Channel Stats */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Channels
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.channel_stats.map((ch) => {
            const uploadedCount = ch.stats.published;
            const publicCount = data.recent_runs.filter(
              (r) => r.channel_id === ch.id && r.youtube_url && r.youtube_privacy === 'public'
            ).length;
            const privateCount = uploadedCount - publicCount;

            return (
              <Link
                key={ch.id}
                to={`/channels/${ch.id}`}
                className="block p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] hover:border-purple-500/50 transition-colors no-underline"
              >
                <p className="text-white font-medium mb-1">{ch.name}</p>
                <p className="text-gray-500 text-xs mb-3">{ch.niche}</p>
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div>
                    <p className="text-green-400 font-semibold text-lg font-mono">
                      {publicCount > 0 ? publicCount : ch.stats.published}
                    </p>
                    <p className="text-gray-500 text-xs">
                      {publicCount > 0 ? 'Public' : 'Published'}
                    </p>
                  </div>
                  {privateCount > 0 && (
                    <div>
                      <p className="text-yellow-400 font-semibold text-lg font-mono">
                        {privateCount}
                      </p>
                      <p className="text-gray-500 text-xs">Private</p>
                    </div>
                  )}
                  <div>
                    <p className="text-blue-400 font-semibold text-lg font-mono">
                      {ch.stats.completed}
                    </p>
                    <p className="text-gray-500 text-xs">Completed</p>
                  </div>
                  <div>
                    <p className="text-red-400 font-semibold text-lg font-mono">
                      {ch.stats.failed}
                    </p>
                    <p className="text-gray-500 text-xs">Failed</p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Recent Runs */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Recent Runs
        </h2>
        {data.recent_runs.length === 0 ? (
          <p className="text-gray-500 text-sm py-8 text-center">No recent runs.</p>
        ) : (
          <div className="rounded-lg border border-[#2a2a2a] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#1a1a1a] text-gray-400 text-xs uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">ID</th>
                  <th className="text-left px-4 py-3 font-medium">Channel</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Score</th>
                  <th className="text-left px-4 py-3 font-medium">Link</th>
                  <th className="text-left px-4 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a2a2a]">
                {data.recent_runs.map((run) => (
                  <tr
                    key={run.id}
                    className="hover:bg-[#1a1a1a] transition-colors cursor-pointer"
                    onClick={() => (window.location.href = `/runs/${run.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-gray-400">
                      #{run.id}
                    </td>
                    <td className="px-4 py-3 text-gray-200">
                      {run.channel_name}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs font-mono">
                      {run.content_type}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-300">
                      {run.review_score != null
                        ? `${run.review_score}/10`
                        : '--'}
                    </td>
                    <td className="px-4 py-3">
                      {run.youtube_url ? (
                        <a
                          href={run.youtube_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors"
                          title={`YouTube (${run.youtube_privacy || 'uploaded'})`}
                        >
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                          </svg>
                          {run.youtube_privacy === 'private' && (
                            <svg className="w-3 h-3 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </a>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {formatDate(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function LoadingSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div>
        <div className="h-8 w-40 bg-[#1a1a1a] rounded" />
        <div className="h-4 w-60 bg-[#1a1a1a] rounded mt-2" />
      </div>
      <div className="flex gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-10 w-32 bg-[#1a1a1a] rounded-lg" />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-[#1a1a1a] rounded-lg" />
        ))}
      </div>
    </div>
  );
}
