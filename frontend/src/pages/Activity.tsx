import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

interface ActivityItem {
  id: number;
  channel_id: number;
  channel_name: string;
  title: string;
  status: string;
  created_at: string | null;
  run_id: number | null;
  attempts: number;
  current_step: string | null;
  started_at: string | null;
  completed_at: string | null;
  youtube_url: string | null;
  youtube_publish_at: string | null;
  form_type: string;
}

export default function Activity() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<ActivityItem[]>({
    queryKey: ['activity'],
    queryFn: () => fetch('/api/activity?limit=100').then(r => r.json()),
    refetchInterval: 10000,
  });

  const clearAll = async () => {
    if (!confirm('Clear all activity? This removes all completed, failed, and rejected items. In-progress items will keep running.')) return;
    await fetch('/api/content-bank/clear-all', { method: 'POST' });
    queryClient.invalidateQueries({ queryKey: ['activity'] });
  };

  if (isLoading) return <div className="animate-pulse h-64 bg-[#1a1a1a] rounded-lg" />;

  const items = data || [];
  const generating = items.filter(i => ['queued', 'locked', 'generating'].includes(i.status));
  const ready = items.filter(i => i.status === 'generated');
  const uploaded = items.filter(i => i.status === 'uploaded');
  const rejected = items.filter(i => i.status === 'rejected');
  const failed = items.filter(i => ['failed', 'skipped', 'cancelled'].includes(i.status));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Activity</h1>
          <p className="text-gray-500 text-sm mt-1">Last 48 hours</p>
        </div>
        {items.length > 0 && (
          <button
            onClick={clearAll}
            className="px-4 py-2 rounded-lg bg-[#2a2a2a] border border-[#3a3a3a] text-gray-400 hover:text-red-400 hover:border-red-400/50 transition-colors text-sm"
          >
            Clear All
          </button>
        )}
      </div>

      {generating.length > 0 && (
        <Section title="In Progress" count={generating.length} color="text-yellow-400">
          {generating.map(item => <ActivityRow key={item.id} item={item} />)}
        </Section>
      )}

      {ready.length > 0 && (
        <Section title="Ready" count={ready.length} color="text-green-400">
          {ready.map(item => <ActivityRow key={item.id} item={item} />)}
        </Section>
      )}

      {uploaded.length > 0 && (
        <Section title="Uploaded" count={uploaded.length} color="text-purple-400">
          {uploaded.map(item => <ActivityRow key={item.id} item={item} />)}
        </Section>
      )}

      {rejected.length > 0 && (
        <Section title="Rejected" count={rejected.length} color="text-red-400">
          {rejected.map(item => <ActivityRow key={item.id} item={item} />)}
        </Section>
      )}

      {failed.length > 0 && (
        <Section title="Failed" count={failed.length} color="text-red-400">
          {failed.map(item => <ActivityRow key={item.id} item={item} />)}
        </Section>
      )}

      {items.length === 0 && (
        <div className="p-8 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-center">
          <p className="text-gray-400">No activity in the last 48 hours</p>
        </div>
      )}
    </div>
  );
}

function Section({ title, count, color, children }: { title: string; count: number; color: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className={`text-sm font-medium ${color} uppercase tracking-wider mb-3`}>
        {title} ({count})
      </h2>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const queryClient = useQueryClient();

  const handleCancel = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Cancel "${item.title}"?`)) return;
    await fetch(`/api/content-bank/${item.id}/cancel`, { method: 'POST' });
    queryClient.invalidateQueries({ queryKey: ['activity'] });
  };

  const handleClear = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await fetch(`/api/content-bank/${item.id}/clear`, { method: 'POST' });
    queryClient.invalidateQueries({ queryKey: ['activity'] });
  };

  const handleRetry = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await fetch(`/api/content-bank/${item.id}/retry`, { method: 'POST' });
    queryClient.invalidateQueries({ queryKey: ['activity'] });
  };
  const statusColors: Record<string, string> = {
    uploaded: 'bg-purple-500/15 text-purple-400',
    generated: 'bg-green-500/15 text-green-400',
    generating: 'bg-yellow-500/15 text-yellow-400',
    locked: 'bg-yellow-500/15 text-yellow-400',
    queued: 'bg-gray-500/15 text-gray-400',
    failed: 'bg-red-500/15 text-red-400',
    rejected: 'bg-red-500/15 text-red-400',
    skipped: 'bg-orange-500/15 text-orange-400',
    cancelled: 'bg-gray-500/15 text-gray-400',
  };

  return (
    <div className="rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${statusColors[item.status] || 'bg-gray-500/15 text-gray-400'}`}>
            {item.status}
          </span>
          {item.form_type === 'long' && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-purple-500/15 text-purple-400 shrink-0">
              LONG
            </span>
          )}
          <span className="text-gray-500 text-xs shrink-0">{item.channel_name}</span>
          <span className="text-gray-200 text-sm truncate">{item.title}</span>
        </div>
      <div className="flex items-center gap-2 shrink-0">
        {item.current_step && ['generating', 'locked', 'running'].includes(item.status) && (
          item.current_step === 'images ready for review' ? (
            <span className="text-green-400 text-xs font-bold">Awaiting image review</span>
          ) : (
            <span className="text-yellow-400 text-xs font-mono">{item.current_step}</span>
          )
        )}
        {item.youtube_url && (
          <a href={item.youtube_url} target="_blank" rel="noopener noreferrer"
            className="text-red-400 hover:text-red-300 text-xs no-underline" onClick={e => e.stopPropagation()}>
            YT
          </a>
        )}
        {item.run_id && (
          <Link to={`/runs/${item.run_id}`} className="text-blue-400 text-xs no-underline hover:text-blue-300">
            #{item.run_id}
          </Link>
        )}
        {['queued', 'locked', 'generating'].includes(item.status) && (
          <button onClick={handleCancel}
            className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-500/15 text-red-400 hover:bg-red-500/30 transition-colors cursor-pointer border-none">
            Cancel
          </button>
        )}
        {['failed', 'rejected'].includes(item.status) && (
          <button onClick={handleRetry}
            className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-yellow-500/15 text-yellow-400 hover:bg-yellow-500/30 transition-colors cursor-pointer border-none">
            Retry
          </button>
        )}
        {['failed', 'rejected', 'skipped', 'cancelled'].includes(item.status) && (
          <button onClick={handleClear}
            className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-gray-500/15 text-gray-400 hover:bg-gray-500/30 transition-colors cursor-pointer border-none">
            Clear
          </button>
        )}
      </div>
      </div>
    </div>
  );
}
