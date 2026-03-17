import { Link } from 'react-router-dom';
import { useRuns, usePublishRun, useRejectRun } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';

export default function ReviewQueue() {
  const { data: runs, isLoading, error } = useRuns({ status: 'completed' });
  const publishMutation = usePublishRun();
  const rejectMutation = useRejectRun();

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-40 bg-[#1a1a1a] rounded" />
        <div className="h-64 bg-[#1a1a1a] rounded-lg" />
      </div>
    );
  }

  if (error) {
    return <p className="text-red-400">Failed to load review queue.</p>;
  }

  const sorted = [...(runs || [])].sort(
    (a, b) => (b.review_score ?? 0) - (a.review_score ?? 0)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Review Queue</h1>
        <p className="text-gray-500 text-sm mt-1">
          Videos pending review, sorted by score
        </p>
      </div>

      {sorted.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500">No videos pending review.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-[#2a2a2a] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#1a1a1a] text-gray-400 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3 font-medium">ID</th>
                <th className="text-left px-4 py-3 font-medium">Channel</th>
                <th className="text-left px-4 py-3 font-medium">Type</th>
                <th className="text-left px-4 py-3 font-medium">Score</th>
                <th className="text-left px-4 py-3 font-medium">Recommendation</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a2a]">
              {sorted.map((run) => (
                <tr key={run.id} className="hover:bg-[#1a1a1a] transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      to={`/runs/${run.id}`}
                      className="font-mono text-purple-400 hover:text-purple-300 no-underline"
                    >
                      #{run.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-200">{run.channel_name}</td>
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                    {run.content_type}
                  </td>
                  <td className="px-4 py-3">
                    <ScorePill score={run.review_score} />
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {run.review_recommendation || '--'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => publishMutation.mutate(run.id)}
                        disabled={publishMutation.isPending}
                        className="px-3 py-1 rounded bg-green-600/20 hover:bg-green-600/30 text-green-400 text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer border border-green-600/30"
                      >
                        Publish
                      </button>
                      <button
                        onClick={() => rejectMutation.mutate(run.id)}
                        disabled={rejectMutation.isPending}
                        className="px-3 py-1 rounded bg-red-600/20 hover:bg-red-600/30 text-red-400 text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer border border-red-600/30"
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScorePill({ score }: { score: number | null }) {
  if (score == null) {
    return <span className="text-gray-500 font-mono text-xs">--</span>;
  }
  const color =
    score >= 8
      ? 'bg-green-500/20 text-green-400'
      : score >= 5
        ? 'bg-yellow-500/20 text-yellow-400'
        : 'bg-red-500/20 text-red-400';
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-mono font-medium ${color}`}>
      {score}/10
    </span>
  );
}
