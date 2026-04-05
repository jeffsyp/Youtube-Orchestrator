const statusConfig: Record<string, { bg: string; text: string; label?: string }> = {
  published: { bg: 'bg-green-500/20', text: 'text-green-400' },
  completed: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  failed: { bg: 'bg-red-500/20', text: 'text-red-400' },
  running: { bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
  pending: { bg: 'bg-gray-500/20', text: 'text-gray-400' },
  pending_review: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'pending review' },
  rejected: { bg: 'bg-red-500/20', text: 'text-red-400' },
};

export default function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || statusConfig.pending;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          status === 'running' ? 'animate-pulse' : ''
        }`}
        style={{
          backgroundColor:
            status === 'published'
              ? '#22c55e'
              : status === 'completed'
                ? '#3b82f6'
                : status === 'failed' || status === 'rejected'
                  ? '#ef4444'
                  : status === 'running'
                    ? '#eab308'
                    : status === 'pending_review'
                      ? '#f97316'
                      : '#6b7280',
        }}
      />
      {config.label || status}
    </span>
  );
}
