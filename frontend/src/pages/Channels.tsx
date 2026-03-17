import { Link } from 'react-router-dom';
import { useChannels } from '../hooks/useApi';

export default function Channels() {
  const { data: channels, isLoading, error } = useChannels();

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-32 bg-[#1a1a1a] rounded" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 bg-[#1a1a1a] rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return <p className="text-red-400">Failed to load channels.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Channels</h1>
        <p className="text-gray-500 text-sm mt-1">Manage your YouTube channels</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {channels?.map((ch) => (
          <Link
            key={ch.id}
            to={`/channels/${ch.id}`}
            className="block p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] hover:border-purple-500/50 transition-colors no-underline"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-white font-semibold text-lg">{ch.name}</h3>
                <p className="text-gray-500 text-sm">{ch.niche}</p>
              </div>
              <span className="px-2 py-1 rounded text-xs font-mono bg-purple-500/15 text-purple-400">
                {ch.pipeline}
              </span>
            </div>
            <p className="text-gray-400 text-sm mb-4 line-clamp-2">
              {ch.description}
            </p>
            <div className="grid grid-cols-4 gap-3 text-center pt-3 border-t border-[#2a2a2a]">
              <StatBox label="Total" value={ch.stats.total} color="text-gray-300" />
              <StatBox label="Published" value={ch.stats.published} color="text-green-400" />
              <StatBox label="Completed" value={ch.stats.completed} color="text-blue-400" />
              <StatBox label="Failed" value={ch.stats.failed} color="text-red-400" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <p className={`font-semibold text-lg font-mono ${color}`}>{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}
