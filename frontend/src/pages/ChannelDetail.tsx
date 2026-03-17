import { Link, useParams } from 'react-router-dom';
import { useChannel, useRuns, useChannelMetrics } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';

export default function ChannelDetail() {
  const { id } = useParams<{ id: string }>();
  const channelId = Number(id);
  const { data: channel, isLoading: loadingChannel } = useChannel(channelId);
  const { data: runs, isLoading: loadingRuns } = useRuns({ channel_id: channelId });
  const { data: ytMetrics } = useChannelMetrics(channelId, channelId > 0);

  if (loadingChannel) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 bg-[#1a1a1a] rounded" />
        <div className="h-4 w-64 bg-[#1a1a1a] rounded" />
        <div className="h-64 bg-[#1a1a1a] rounded-lg" />
      </div>
    );
  }

  if (!channel) {
    return <p className="text-red-400">Channel not found.</p>;
  }

  // Count public vs private from runs data
  const publishedRuns = runs?.filter((r) => r.youtube_url) ?? [];
  const publicCount = publishedRuns.filter((r) => r.youtube_privacy === 'public').length;
  const privateCount = publishedRuns.filter((r) => r.youtube_privacy === 'private').length;
  const unlistedCount = publishedRuns.filter((r) => r.youtube_privacy === 'unlisted').length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link to="/channels" className="text-gray-500 text-sm hover:text-gray-300 no-underline">
          &larr; Channels
        </Link>
        <h1 className="text-2xl font-semibold text-white mt-2">{channel.name}</h1>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-gray-400 text-sm">{channel.niche}</span>
          <span className="text-gray-600">|</span>
          <span className="px-2 py-0.5 rounded text-xs font-mono bg-purple-500/15 text-purple-400">
            {channel.pipeline}
          </span>
        </div>
        {channel.description && (
          <p className="text-gray-400 text-sm mt-3 max-w-2xl">
            {channel.description}
          </p>
        )}
      </div>

      {/* YouTube Metrics */}
      {ytMetrics && ytMetrics.video_count > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            YouTube Performance
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Total Views"
              value={formatNumber(ytMetrics.total_views)}
              color="text-blue-400"
            />
            <MetricCard
              label="Total Likes"
              value={formatNumber(ytMetrics.total_likes)}
              color="text-green-400"
            />
            <MetricCard
              label="Videos Tracked"
              value={String(ytMetrics.video_count)}
              color="text-purple-400"
            />
            <MetricCard
              label="Avg Views/Video"
              value={formatNumber(Math.round(ytMetrics.avg_views_per_video))}
              color="text-cyan-400"
            />
          </div>
        </section>
      )}

      {/* Pipeline Stats */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Pipeline Stats
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Total" value={channel.stats.total} color="text-gray-300" />
          {publicCount > 0 ? (
            <StatCard label="Public" value={publicCount} color="text-green-400" />
          ) : (
            <StatCard label="Published" value={channel.stats.published} color="text-green-400" />
          )}
          {privateCount > 0 && (
            <StatCard label="Private" value={privateCount} color="text-yellow-400" />
          )}
          {unlistedCount > 0 && (
            <StatCard label="Unlisted" value={unlistedCount} color="text-blue-400" />
          )}
          <StatCard label="Completed" value={channel.stats.completed} color="text-blue-400" />
          <StatCard label="Failed" value={channel.stats.failed} color="text-red-400" />
        </div>
      </section>

      {/* Runs */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Runs
        </h2>
        {loadingRuns ? (
          <div className="animate-pulse h-48 bg-[#1a1a1a] rounded-lg" />
        ) : !runs || runs.length === 0 ? (
          <p className="text-gray-500 text-sm py-8 text-center">No runs yet.</p>
        ) : (
          <div className="rounded-lg border border-[#2a2a2a] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#1a1a1a] text-gray-400 text-xs uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">ID</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Score</th>
                  <th className="text-left px-4 py-3 font-medium">Link</th>
                  <th className="text-left px-4 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a2a2a]">
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="hover:bg-[#1a1a1a] transition-colors cursor-pointer"
                    onClick={() => (window.location.href = `/runs/${run.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-gray-400">#{run.id}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs font-mono">
                      {run.content_type}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={run.status} />
                        {run.youtube_privacy && (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                            run.youtube_privacy === 'public'
                              ? 'bg-green-500/15 text-green-400'
                              : run.youtube_privacy === 'unlisted'
                              ? 'bg-blue-500/15 text-blue-400'
                              : 'bg-yellow-500/15 text-yellow-400'
                          }`}>
                            {run.youtube_privacy}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-300">
                      {run.review_score != null ? `${run.review_score}/10` : '--'}
                    </td>
                    <td className="px-4 py-3">
                      {run.youtube_url ? (
                        <a
                          href={run.youtube_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center text-red-400 hover:text-red-300 transition-colors"
                          title="Watch on YouTube"
                        >
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                          </svg>
                        </a>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {new Date(run.started_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
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

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-center">
      <p className={`font-semibold text-2xl font-mono ${color}`}>{value}</p>
      <p className="text-gray-500 text-xs mt-1">{label}</p>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-center">
      <p className={`font-semibold text-2xl font-mono ${color}`}>{value}</p>
      <p className="text-gray-500 text-xs mt-1">{label}</p>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
