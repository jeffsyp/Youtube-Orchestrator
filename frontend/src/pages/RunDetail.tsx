import { Link, useParams } from 'react-router-dom';
import { useRunDetail, usePublishRun, useDeleteRun, useRunMetrics } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import VideoPlayer from '../components/VideoPlayer';
import ReviewScores from '../components/ReviewScores';

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);
  const { data: run, isLoading, error } = useRunDetail(runId);
  const publishMutation = usePublishRun();
  const deleteMutation = useDeleteRun();
  const hasYoutubeUrl = !!run?.youtube_url;
  const { data: metrics } = useRunMetrics(runId, hasYoutubeUrl);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 bg-[#1a1a1a] rounded" />
        <div className="aspect-video bg-[#1a1a1a] rounded-lg" />
        <div className="h-32 bg-[#1a1a1a] rounded-lg" />
      </div>
    );
  }

  if (error || !run) {
    return <p className="text-red-400">Failed to load run details.</p>;
  }

  const canPublish = run.status === 'completed';
  const canDelete = run.status !== 'running';

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link to="/" className="text-gray-500 text-sm hover:text-gray-300 no-underline">
          &larr; Dashboard
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Run <span className="font-mono">#{run.id}</span>
            </h1>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-gray-400 text-sm">{run.channel_name}</span>
              <span className="text-gray-600">|</span>
              <span className="text-gray-400 text-xs font-mono">{run.content_type}</span>
              <StatusBadge status={run.status} />
              {run.youtube_privacy && (
                <span className={`px-2 py-0.5 rounded text-xs font-mono ${
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
          </div>
          <div className="flex gap-3">
            {run.youtube_url && (
              <a
                href={run.youtube_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors no-underline"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                Watch on YouTube
              </a>
            )}
            {canPublish && (
              <button
                onClick={() => publishMutation.mutate(runId)}
                disabled={publishMutation.isPending}
                className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer"
              >
                {publishMutation.isPending ? 'Publishing...' : 'Publish'}
              </button>
            )}
            {canDelete && (
              <button
                onClick={() => {
                  if (confirm('Are you sure you want to delete this run?')) {
                    deleteMutation.mutate(runId);
                  }
                }}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-400 text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer border border-red-600/30"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error message */}
      {run.error && (
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30">
          <p className="text-red-400 text-sm font-medium mb-1">Error</p>
          <p className="text-red-300 text-sm font-mono">{run.error}</p>
        </div>
      )}

      {/* Video Player */}
      {run.video_path && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Video
          </h2>
          <VideoPlayer runId={run.id} thumbnailPath={run.thumbnail_path} />
        </section>
      )}

      {/* YouTube Metrics */}
      {run.youtube_url && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            YouTube Metrics
          </h2>
          {metrics ? (
            <div className="grid grid-cols-3 gap-4">
              <MetricCard label="Views" value={formatNumber(metrics.views)} color="text-blue-400" />
              <MetricCard label="Likes" value={formatNumber(metrics.likes)} color="text-green-400" />
              <MetricCard label="Comments" value={formatNumber(metrics.comments)} color="text-purple-400" />
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
              <p className="text-gray-500 text-sm">
                {run.youtube_privacy === 'private'
                  ? 'Metrics are limited for private videos.'
                  : 'No metrics available yet.'}
              </p>
            </div>
          )}
        </section>
      )}

      {/* Info Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Run Info */}
        <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Details
          </h3>
          <dl className="space-y-3">
            <InfoRow label="Status" value={run.status} />
            {run.current_step && <InfoRow label="Current Step" value={run.current_step} mono />}
            <InfoRow label="Started" value={formatDate(run.started_at)} />
            {run.completed_at && <InfoRow label="Completed" value={formatDate(run.completed_at)} />}
            {run.elapsed_seconds != null && (
              <InfoRow label="Duration" value={formatElapsed(run.elapsed_seconds)} mono />
            )}
            {run.review_score != null && (
              <InfoRow label="Score" value={`${run.review_score}/10`} mono />
            )}
            {run.review_recommendation && (
              <InfoRow label="Recommendation" value={run.review_recommendation} />
            )}
            {run.youtube_url && (
              <InfoRow label="YouTube" value={run.youtube_url} mono />
            )}
          </dl>
        </div>

        {/* Review Scores */}
        <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Review Scores
          </h3>
          <ReviewScores review={run.review} />
        </div>
      </div>

      {/* Ideas */}
      {run.ideas && run.ideas.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Ideas
          </h2>
          <div className="space-y-3">
            {run.ideas.map((idea) => (
              <div
                key={idea.id}
                className="p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]"
              >
                <div className="flex items-start justify-between">
                  <h4 className="text-white font-medium">{idea.title}</h4>
                  {idea.score != null && (
                    <span className="text-purple-400 font-mono text-sm">
                      {idea.score}/10
                    </span>
                  )}
                </div>
                <p className="text-gray-400 text-sm mt-1">{idea.hook}</p>
                {idea.angle && (
                  <p className="text-gray-500 text-xs mt-2">Angle: {idea.angle}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
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

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <dt className="text-gray-500 text-sm">{label}</dt>
      <dd className={`text-gray-200 text-sm ${mono ? 'font-mono' : ''} max-w-[300px] truncate`}>{value}</dd>
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
