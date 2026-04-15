import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useRunDetail, useRunMetrics, usePublishRun, useRejectRun, useCancelRun } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import VideoPlayer from '../components/VideoPlayer';
import ReviewScores from '../components/ReviewScores';

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);
  const { data: run, isLoading, error } = useRunDetail(runId);
  const hasYoutubeUrl = !!run?.youtube_url;
  const { data: metrics } = useRunMetrics(runId, hasYoutubeUrl);
  const publishMutation = usePublishRun();
  const rejectMutation = useRejectRun();
  const cancelMutation = useCancelRun();
  const [privacy, setPrivacy] = useState<string>('private');

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

  // Extract review data from assets
  const reviewAsset = run.assets?.find((a) => a.asset_type === 'video_review');
  let reviewData: Record<string, unknown> | null = null;
  if (reviewAsset?.content) {
    try {
      const parsed = JSON.parse(reviewAsset.content);
      if (parsed.reviewed) {
        reviewData = {
          scores: {
            scroll_test: parsed.scroll_test_score,
            rewatch: parsed.rewatch_score,
            promise: parsed.promise_score,
            visual_quality: parsed.quality_score,
            entertainment: parsed.entertainment_score,
            overall: parsed.overall_score,
          },
          summary: parsed.summary,
          top_issue: parsed.top_issue,
          suggestions: parsed.suggestions,
        };
      }
    } catch {
      // ignore
    }
  }

  // Extract production QA from assets
  const prodQaAsset = run.assets?.find((a) => a.asset_type === 'production_qa');
  let prodQa: Record<string, unknown> | null = null;
  if (prodQaAsset?.content) {
    try {
      const parsed = JSON.parse(prodQaAsset.content);
      if (parsed.reviewed) prodQa = parsed;
    } catch {
      // ignore
    }
  }

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
              {run.title || `Run #${run.id}`}
            </h1>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-gray-400 text-xs font-mono">#{run.id}</span>
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
          <div className="flex items-center gap-3">
            {/* Cancel button for running runs */}
            {run.status === 'running' && (
              <button
                onClick={() => cancelMutation.mutate(runId)}
                className="px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-400 text-sm font-medium transition-colors"
              >
                Cancel
              </button>
            )}
            {/* Upload button for pending_review runs */}
            {run.status === 'pending_review' && (
              <>
                <select
                  value={privacy}
                  onChange={(e) => setPrivacy(e.target.value)}
                  className="px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-gray-200 text-sm"
                >
                  <option value="private">Private</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="public">Public</option>
                  <option value="scheduled">Scheduled (1-3 hrs)</option>
                </select>
                <button
                  onClick={() => publishMutation.mutate({ id: runId, privacy: privacy === 'scheduled' ? 'scheduled' : privacy })}
                  disabled={publishMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 disabled:bg-green-800 disabled:cursor-wait text-white text-sm font-medium transition-colors"
                >
                  {publishMutation.isPending ? 'Uploading...' : privacy === 'scheduled' ? 'Schedule Upload' : 'Upload to YouTube'}
                </button>
                <button
                  onClick={() => { if (confirm('Reject this video? Output files will be deleted.')) rejectMutation.mutate(runId); }}
                  disabled={rejectMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-400 text-sm font-medium transition-colors"
                >
                  {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                </button>
              </>
            )}
            {/* YouTube link for uploaded runs */}
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
          </div>
        </div>
      </div>

      {/* Upload/Reject feedback */}
      {publishMutation.isSuccess && (
        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/30">
          <p className="text-green-400 text-sm font-medium">Uploaded successfully! Refresh to see YouTube link.</p>
        </div>
      )}
      {publishMutation.isError && (
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30">
          <p className="text-red-400 text-sm font-medium">Upload failed: {(publishMutation.error as Error)?.message}</p>
        </div>
      )}
      {rejectMutation.isSuccess && (
        <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/30">
          <p className="text-orange-400 text-sm font-medium">Video rejected and files deleted.</p>
        </div>
      )}

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
            {run.last_change && <InfoRow label="Last Change" value={run.last_change} mono />}
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

        {/* Image Review */}
        <ImageReview runId={runId} currentStep={run.current_step} />

        {/* Pipeline Logs */}
        <RunLogs runId={runId} status={run.status} />

        {/* Review Scores */}
        <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Review Scores
          </h3>
          <ReviewScores review={reviewData} />
        </div>
      </div>

      {/* Production QA */}
      {prodQa && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
            Production QA
          </h2>
          <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] space-y-4">
            {/* Verdict */}
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                prodQa.verdict === 'pass'
                  ? 'bg-green-500/15 text-green-400'
                  : 'bg-orange-500/15 text-orange-400'
              }`}>
                {prodQa.verdict === 'pass' ? 'Pass' : 'Needs Fixes'}
              </span>
              {prodQa.biggest_issue && (
                <span className="text-gray-300 text-sm">{prodQa.biggest_issue as string}</span>
              )}
            </div>

            {/* Issue categories */}
            <ProductionIssueList label="Flow Issues" items={prodQa.flow_issues as string[]} color="text-yellow-400" />
            <ProductionIssueList label="Story Issues" items={prodQa.story_issues as string[]} color="text-blue-400" />
            <ProductionIssueList label="Character Issues" items={prodQa.character_issues as string[]} color="text-purple-400" />

            {/* Script vs Video comparison */}
            {(prodQa.script_vs_video as Array<Record<string, unknown>>)?.length > 0 && (
              <div>
                <p className="text-sm font-medium text-orange-400 mb-2">Script vs Video</p>
                <div className="space-y-3">
                  {(prodQa.script_vs_video as Array<Record<string, unknown>>).map((item, i) => (
                    <div key={i} className="p-3 rounded bg-[#0f0f0f] space-y-1.5">
                      <p className="text-xs font-mono text-gray-500">Clip {item.clip as number}</p>
                      <div className="flex gap-2">
                        <span className="text-red-400 text-xs shrink-0">Script:</span>
                        <p className="text-gray-400 text-xs">{item.script_said as string}</p>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-yellow-400 text-xs shrink-0">Video:</span>
                        <p className="text-gray-400 text-xs">{item.video_showed as string}</p>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-green-400 text-xs shrink-0">Fix:</span>
                        <p className="text-green-300 text-xs">{item.rewritten_prompt as string}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Fix suggestions */}
            {(prodQa.fix_suggestions as string[])?.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-400 mb-2">Suggested Fixes</p>
                <ol className="list-decimal list-inside space-y-1">
                  {(prodQa.fix_suggestions as string[]).map((s, i) => (
                    <li key={i} className="text-sm text-gray-300">{s}</li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function ProductionIssueList({ label, items, color }: { label: string; items?: string[]; color: string }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className={`text-sm font-medium ${color} mb-1`}>{label}</p>
      <ul className="space-y-0.5 ml-3">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-gray-300 before:content-['•'] before:mr-2 before:text-gray-600">
            {item}
          </li>
        ))}
      </ul>
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

function RunLogs({ runId, status }: { runId: number; status: string }) {
  const isActive = ['running', 'generating', 'locked'].includes(status);

  const { data } = useQuery<{ logs: string[]; current_step: string | null }>({
    queryKey: ['run-logs', runId],
    queryFn: () => fetch(`/api/runs/${runId}/logs`).then(r => r.json()),
    refetchInterval: isActive ? 5000 : false,
  });

  const logs = data?.logs || [];
  if (logs.length === 0) return null;

  return (
    <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
        Pipeline Logs {isActive && <span className="text-green-400 animate-pulse ml-2">LIVE</span>}
      </h3>
      <div className="max-h-60 overflow-y-auto rounded bg-[#111] p-3 space-y-0.5">
        {logs.map((line, i) => (
          <div key={i} className="text-[11px] font-mono text-gray-400 leading-5">{line}</div>
        ))}
      </div>
    </div>
  );
}

function ImageReview({ runId, currentStep }: { runId: number; currentStep: string | null }) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [denied, setDenied] = useState<Set<string>>(new Set());
  const [approving, setApproving] = useState(false);

  const { data, refetch } = useQuery<{ images: { name: string; b64: string }[]; total: number }>({
    queryKey: ['run-images', runId],
    queryFn: () => fetch(`/api/runs/${runId}/images`).then(r => r.ok ? r.json() : { images: [], total: 0 }),
    refetchInterval: currentStep === 'images ready for review' ? 3000 : false,
  });

  const images = data?.images || [];
  if (images.length === 0) return null;

  const toggleDeny = (name: string) => {
    const next = new Set(denied);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setDenied(next);
  };

  const approveAll = async () => {
    setApproving(true);
    await fetch(`/api/runs/${runId}/images/approve-all`, { method: 'POST' });
    setApproving(false);
    refetch();
  };

  const submitReview = async () => {
    setApproving(true);
    const deniedList = Array.from(denied).map(name => ({
      name,
      feedback: feedback[name] || 'Regenerate this image',
    }));
    const approvedList = images.filter(img => !denied.has(img.name)).map(img => img.name);
    await fetch(`/api/runs/${runId}/images/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: approvedList, denied: deniedList }),
    });
    setApproving(false);
    setDenied(new Set());
    setFeedback({});
    refetch();
  };

  return (
    <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
          Scene Images ({images.length})
        </h3>
        <div className="flex gap-2">
          {denied.size > 0 && (
            <button
              onClick={submitReview}
              disabled={approving}
              className="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
            >
              {approving ? '...' : `Deny ${denied.size} & Regenerate`}
            </button>
          )}
          <button
            onClick={approveAll}
            disabled={approving}
            className="px-3 py-1 text-xs rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
          >
            {approving ? '...' : 'Approve All'}
          </button>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {images.map((img) => (
          <div
            key={img.name}
            className={`relative rounded border-2 cursor-pointer transition-all ${
              denied.has(img.name) ? 'border-red-500 opacity-60' : 'border-transparent hover:border-blue-500'
            }`}
            onClick={() => toggleDeny(img.name)}
          >
            <img
              src={`data:image/png;base64,${img.b64}`}
              alt={img.name}
              className="w-full rounded"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1">
              <span className="text-[10px] text-gray-300 font-mono">{img.name}</span>
            </div>
            {denied.has(img.name) && (
              <div className="absolute inset-0 flex items-center justify-center bg-red-900/30 rounded">
                <span className="text-red-300 font-bold text-sm">DENIED</span>
              </div>
            )}
          </div>
        ))}
      </div>
      {denied.size > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-gray-400">Feedback for denied images:</p>
          {Array.from(denied).map(name => (
            <div key={name} className="flex gap-2 items-center">
              <span className="text-xs text-red-400 font-mono w-32 shrink-0">{name}</span>
              <input
                type="text"
                placeholder="What should change?"
                value={feedback[name] || ''}
                onChange={(e) => setFeedback(prev => ({ ...prev, [name]: e.target.value }))}
                className="flex-1 px-2 py-1 text-xs bg-[#111] border border-[#333] rounded text-gray-200 placeholder-gray-600"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
