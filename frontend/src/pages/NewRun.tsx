import { useState } from 'react';
import { useChannels, useStartBatchRuns } from '../hooks/useApi';

export default function NewRun() {
  const { data: channels, isLoading } = useChannels();
  const batchMutation = useStartBatchRuns();
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [privacy, setPrivacy] = useState('private');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const toggleChannel = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const startAll = () => {
    if (selectedIds.size === 0) return;
    batchMutation.mutate(
      { channel_ids: Array.from(selectedIds), privacy },
      {
        onSuccess: (data) => {
          setSuccessMessage(`Started ${data.started.length} run(s)`);
          setSelectedIds(new Set());
          setTimeout(() => setSuccessMessage(null), 3000);
        },
      }
    );
  };

  const startSingle = (channelId: number) => {
    batchMutation.mutate(
      { channel_ids: [channelId], privacy },
      {
        onSuccess: () => {
          setSuccessMessage('Run started');
          setTimeout(() => setSuccessMessage(null), 3000);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-32 bg-[#1a1a1a] rounded" />
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-[#1a1a1a] rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold text-white">New Run</h1>
        <p className="text-gray-500 text-sm mt-1">Start new video pipeline runs</p>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-sm">
          {successMessage}
        </div>
      )}

      {/* Error message */}
      {batchMutation.isError && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          Failed to start runs. Check that the backend is running.
        </div>
      )}

      {/* Privacy setting */}
      <div>
        <label className="block text-sm text-gray-400 mb-2">Privacy</label>
        <select
          value={privacy}
          onChange={(e) => setPrivacy(e.target.value)}
          className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-purple-500"
        >
          <option value="private">Private</option>
          <option value="unlisted">Unlisted</option>
          <option value="public">Public</option>
        </select>
      </div>

      {/* Channel selection */}
      <div className="space-y-3">
        <label className="block text-sm text-gray-400">Select Channels</label>
        {channels?.map((ch) => (
          <div
            key={ch.id}
            className={`p-4 rounded-lg border transition-colors ${
              selectedIds.has(ch.id)
                ? 'bg-purple-600/10 border-purple-500/50'
                : 'bg-[#1a1a1a] border-[#2a2a2a]'
            }`}
          >
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-3 cursor-pointer flex-1">
                <input
                  type="checkbox"
                  checked={selectedIds.has(ch.id)}
                  onChange={() => toggleChannel(ch.id)}
                  className="w-4 h-4 rounded border-gray-600 accent-purple-600"
                />
                <div>
                  <p className="text-white font-medium text-sm">{ch.name}</p>
                  <p className="text-gray-500 text-xs">
                    {ch.niche} &middot; {ch.pipeline}
                  </p>
                </div>
              </label>
              <button
                onClick={() => startSingle(ch.id)}
                disabled={batchMutation.isPending}
                className="px-3 py-1.5 rounded-lg bg-[#2a2a2a] hover:bg-[#333] text-gray-300 text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
              >
                Start
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Start All button */}
      <button
        onClick={startAll}
        disabled={selectedIds.size === 0 || batchMutation.isPending}
        className="w-full py-3 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      >
        {batchMutation.isPending
          ? 'Starting...'
          : `Start ${selectedIds.size > 0 ? selectedIds.size : ''} Selected`}
      </button>
    </div>
  );
}
