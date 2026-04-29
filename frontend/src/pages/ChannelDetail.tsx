import { useParams, Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useRuns, useSchedule, useContentBank, useGenerateNow } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import { useState } from 'react';

export default function ChannelDetail() {
  const { id } = useParams<{ id: string }>();
  const channelId = Number(id);
  const qc = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [conceptJson, setConceptJson] = useState('');

  const { data: schedule } = useSchedule(channelId);
  const { data: queue } = useContentBank({ channel_id: channelId, status: 'all' });
  const { data: runs } = useRuns({ channel_id: channelId, limit: 20 });
  const generateNow = useGenerateNow();

  const pauseMutation = useMutation({
    mutationFn: () => api.pauseChannel(channelId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  });

  const resumeMutation = useMutation({
    mutationFn: () => api.resumeChannel(channelId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (bankId: number) => api.deleteContentBankItem(bankId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['content-bank'] }),
  });

  const addMutation = useMutation({
    mutationFn: (item: { channel_id: number; title: string; concept_json: unknown }) =>
      api.addToContentBank(item),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['content-bank'] });
      setShowAddForm(false);
      setConceptJson('');
    },
  });

  const channelName = schedule?.channel_name || `Channel ${channelId}`;

  return (
    <div className="space-y-8">
      <div>
        <Link to="/" className="text-gray-500 text-sm hover:text-gray-300 no-underline">
          &larr; Dashboard
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-2xl font-semibold text-white">{channelName}</h1>
            <p className="text-gray-500 text-sm mt-1">
              {schedule?.videos_per_day || 0} videos/day &middot; Queue: {schedule?.queue_depth || 0} &middot; Today: {schedule?.today_count || 0}
            </p>
          </div>
          <div className="flex gap-2">
            {schedule?.paused ? (
              <button
                onClick={() => resumeMutation.mutate()}
                className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium cursor-pointer"
              >
                Resume
              </button>
            ) : (
              <button
                onClick={() => pauseMutation.mutate()}
                className="px-4 py-2 rounded-lg bg-yellow-600 hover:bg-yellow-500 text-white text-sm font-medium cursor-pointer"
              >
                Pause
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Schedule Config */}
      {schedule && (
        <section className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Schedule</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Videos/Day</p>
              <p className="text-white font-mono">{schedule.videos_per_day}</p>
            </div>
            <div>
              <p className="text-gray-500">Auto Upload</p>
              <p className={schedule.auto_upload ? 'text-green-400' : 'text-gray-400'}>{schedule.auto_upload ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <p className="text-gray-500">Privacy</p>
              <p className="text-white font-mono">{schedule.upload_privacy}</p>
            </div>
            <div>
              <p className="text-gray-500">Status</p>
              <p className={schedule.paused ? 'text-yellow-400' : 'text-green-400'}>{schedule.paused ? 'Paused' : 'Active'}</p>
            </div>
          </div>
          {schedule.time_windows?.length > 0 && (
            <div className="mt-3">
              <p className="text-gray-500 text-sm">Time Windows</p>
              <div className="flex gap-2 mt-1">
                {schedule.time_windows.map((w, i) => (
                  <span key={i} className="px-2 py-1 rounded bg-[#2a2a2a] text-gray-300 text-xs font-mono">
                    {w.start} - {w.end}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Content Queue */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Content Queue</h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium cursor-pointer"
          >
            + Add Concept
          </button>
        </div>

        {showAddForm && (
          <div className="mb-4 p-4 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] space-y-3">
            <textarea
              value={conceptJson}
              onChange={(e) => setConceptJson(e.target.value)}
              placeholder="Paste concept JSON here..."
              className="w-full h-40 p-3 rounded bg-[#0f0f0f] border border-[#2a2a2a] text-gray-200 text-sm font-mono resize-y"
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  try {
                    const parsed = JSON.parse(conceptJson);
                    addMutation.mutate({
                      channel_id: channelId,
                      title: parsed.title || 'Untitled',
                      concept_json: parsed,
                    });
                  } catch { /* ignore parse error */ }
                }}
                className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium cursor-pointer"
              >
                Add to Queue
              </button>
              <button
                onClick={() => { setShowAddForm(false); setConceptJson(''); }}
                className="px-4 py-2 rounded-lg bg-[#2a2a2a] text-gray-400 text-sm cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {(!queue || queue.length === 0) ? (
          <p className="text-gray-500 text-sm py-4 text-center">Queue is empty.</p>
        ) : (
          <div className="space-y-2">
            {queue.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-3 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span className="text-gray-600 text-xs font-mono shrink-0">P{item.priority}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                    item.status === 'queued' ? 'bg-blue-500/15 text-blue-400' :
                    item.status === 'generating' ? 'bg-yellow-500/15 text-yellow-400' :
                    item.status === 'generated' ? 'bg-green-500/15 text-green-400' :
                    item.status === 'uploaded' ? 'bg-purple-500/15 text-purple-400' :
                    item.status === 'failed' ? 'bg-red-500/15 text-red-400' :
                    'bg-gray-500/15 text-gray-400'
                  }`}>{item.status}</span>
                  <span className="text-gray-200 text-sm truncate">{item.title}</span>
                  {item.error && <span className="text-red-400 text-xs truncate max-w-[200px]">{item.error}</span>}
                </div>
                <div className="flex gap-1.5 shrink-0">
                  {item.status === 'queued' && (
                    <button
                      onClick={() => generateNow.mutate(item.id)}
                      className="px-2 py-1 rounded text-xs text-green-400 hover:bg-green-500/10 cursor-pointer"
                    >
                      Generate Now
                    </button>
                  )}
                  {item.run_id && (
                    <Link
                      to={`/runs/${item.run_id}`}
                      className="px-2 py-1 rounded text-xs text-blue-400 hover:bg-blue-500/10 no-underline"
                    >
                      View Run
                    </Link>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(item.id)}
                    className="px-2 py-1 rounded text-xs text-red-400 hover:bg-red-500/10 cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Runs */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Recent Runs</h2>
        {(!runs || runs.length === 0) ? (
          <p className="text-gray-500 text-sm py-4 text-center">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="flex items-center justify-between p-3 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] hover:border-[#3a3a3a] transition-colors no-underline"
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-xs font-mono">#{run.id}</span>
                  <StatusBadge status={run.status} />
                  <span className="text-gray-200 text-sm">{run.title || '--'}</span>
                </div>
                <div className="flex items-center gap-2">
                  {run.youtube_url && (
                    <span className="text-red-400 text-xs">YT</span>
                  )}
                  <span className="text-gray-500 text-xs">
                    {run.started_at ? new Date(run.started_at).toLocaleDateString() : ''}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
