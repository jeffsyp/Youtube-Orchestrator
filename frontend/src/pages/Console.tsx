import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useContentBank, useReviewTasks, useRuns } from '../hooks/useApi';
import type { ContentBankItem, ReviewTask } from '../api/types';
import StatusBadge from '../components/StatusBadge';

export default function Console() {
  const queryClient = useQueryClient();
  const { data: queue } = useContentBank({ status: 'all' });
  const { data: reviewTasks } = useReviewTasks({ status: 'pending', kind: 'images', limit: 20 });
  const { data: runs } = useRuns({ limit: 30 });
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  useEffect(() => {
    const source = new EventSource('/api/events/stream');
    const refresh = () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      queryClient.invalidateQueries({ queryKey: ['review-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['content-bank'] });
    };
    source.onmessage = refresh;
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [queryClient]);

  const activeRuns = (runs || []).filter((run) => ['running', 'blocked', 'pending_review'].includes(run.status));
  const selectedRun = useMemo(
    () => (runs || []).find((run) => run.id === selectedRunId) || activeRuns[0] || (runs || [])[0] || null,
    [runs, activeRuns, selectedRunId],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Operator Console</h1>
          <p className="text-gray-500 text-sm mt-1">
            One place for queued concepts, review tasks, and live runs.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <SummaryPill label="Queued" value={(queue || []).filter((item) => item.status === 'queued').length} color="text-blue-400" />
          <SummaryPill label="Review" value={(reviewTasks || []).length} color="text-green-400" />
          <SummaryPill label="Active" value={activeRuns.length} color="text-yellow-400" />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr_1.1fr] gap-6">
        <section className="p-4 rounded-xl bg-[#161616] border border-[#272727]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Queue</h2>
            <Link to="/concepts" className="text-xs text-blue-400 no-underline hover:text-blue-300">Concepts</Link>
          </div>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {(queue || []).slice(0, 20).map((item) => (
              <QueueRow key={item.id} item={item} onSelectRun={setSelectedRunId} />
            ))}
            {(!queue || queue.length === 0) && (
              <p className="text-sm text-gray-500">No queue items.</p>
            )}
          </div>
        </section>

        <section className="p-4 rounded-xl bg-[#161616] border border-[#272727]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Review Inbox</h2>
            <Link to="/review" className="text-xs text-blue-400 no-underline hover:text-blue-300">Open Review</Link>
          </div>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {(reviewTasks || []).map((task) => (
              <ReviewRow key={task.id} task={task} onSelectRun={setSelectedRunId} />
            ))}
            {(!reviewTasks || reviewTasks.length === 0) && (
              <p className="text-sm text-gray-500">No pending review tasks.</p>
            )}
          </div>
        </section>

        <section className="p-4 rounded-xl bg-[#161616] border border-[#272727]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Run Focus</h2>
            {selectedRun && (
              <Link to={`/runs/${selectedRun.id}`} className="text-xs text-blue-400 no-underline hover:text-blue-300">
                Open Full Run
              </Link>
            )}
          </div>
          {selectedRun ? (
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-[#101010] border border-[#222]">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-gray-500 text-xs font-mono">#{selectedRun.id}</span>
                  <StatusBadge status={selectedRun.status} />
                  <span className="text-gray-500 text-xs">{selectedRun.channel_name}</span>
                </div>
                <h3 className="text-white font-medium text-sm">{selectedRun.title || 'Untitled run'}</h3>
                {selectedRun.current_step && (
                  <p className="text-yellow-400 text-xs font-mono mt-2">{selectedRun.current_step}</p>
                )}
                {selectedRun.last_change && (
                  <p className="text-gray-400 text-xs mt-2">{selectedRun.last_change}</p>
                )}
                {selectedRun.error && (
                  <p className="text-red-400 text-xs mt-2">{selectedRun.error}</p>
                )}
              </div>

              <div>
                <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-2">Recent Runs</h3>
                <div className="space-y-2">
                  {(runs || []).slice(0, 10).map((run) => (
                    <button
                      key={run.id}
                      onClick={() => setSelectedRunId(run.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        run.id === selectedRun.id
                          ? 'bg-green-500/10 border-green-500/30'
                          : 'bg-[#101010] border-[#222] hover:border-[#333]'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-gray-500 text-[11px] font-mono">#{run.id}</span>
                        <span className="text-gray-400 text-[11px]">{run.channel_name}</span>
                      </div>
                      <div className="text-sm text-gray-200 truncate">{run.title || 'Untitled'}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No runs yet.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function SummaryPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="px-3 py-2 rounded-lg bg-[#161616] border border-[#272727]">
      <span className={`font-semibold ${color}`}>{value}</span>
      <span className="text-gray-500 ml-2">{label}</span>
    </div>
  );
}

function QueueRow({ item, onSelectRun }: { item: ContentBankItem; onSelectRun: (runId: number | null) => void }) {
  return (
    <div className="p-3 rounded-lg bg-[#101010] border border-[#222]">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] text-gray-500 mb-1">{item.channel_name}</p>
          <p className="text-sm text-gray-200 truncate">{item.title}</p>
        </div>
        <span className="text-[11px] text-blue-400 font-mono shrink-0">P{item.priority}</span>
      </div>
      <div className="flex items-center justify-between mt-2">
        <StatusBadge status={item.status} />
        {item.run_id ? (
          <button onClick={() => onSelectRun(item.run_id)} className="text-xs text-blue-400 bg-transparent border-0 cursor-pointer">
            Focus Run
          </button>
        ) : (
          <span className="text-[11px] text-gray-600">{item.attempt_count} attempts</span>
        )}
      </div>
    </div>
  );
}

function ReviewRow({ task, onSelectRun }: { task: ReviewTask; onSelectRun: (runId: number | null) => void }) {
  const expected = Number(task.payload.expected_images || 0);
  return (
    <button
      onClick={() => onSelectRun(task.run_id)}
      className="w-full text-left p-3 rounded-lg bg-[#101010] border border-[#222] hover:border-[#333] transition-colors"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] text-gray-500 mb-1">{task.channel_name}</p>
          <p className="text-sm text-gray-200 truncate">{task.title || `Run #${task.run_id}`}</p>
        </div>
        <span className="px-2 py-1 rounded bg-green-500/10 text-green-400 text-[11px] font-medium shrink-0">
          {task.kind}
        </span>
      </div>
      <div className="flex items-center justify-between mt-2 text-[11px] text-gray-500">
        <span>{task.current_step || 'awaiting review'}</span>
        {expected > 0 && <span>{expected} images</span>}
      </div>
    </button>
  );
}
