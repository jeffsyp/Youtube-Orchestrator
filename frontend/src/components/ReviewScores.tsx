interface ReviewScoresProps {
  review: Record<string, unknown> | null;
}

const dimensionColors: Record<string, string> = {
  visual_quality: '#7c3aed',
  audio_quality: '#3b82f6',
  pacing: '#22c55e',
  engagement: '#eab308',
  accuracy: '#ef4444',
  overall: '#ec4899',
};

export default function ReviewScores({ review }: ReviewScoresProps) {
  if (!review) {
    return <p className="text-gray-500 text-sm">No review data available.</p>;
  }

  const scores = review.scores as Record<string, number> | undefined;
  if (!scores) {
    return <p className="text-gray-500 text-sm">No scores available.</p>;
  }

  return (
    <div className="space-y-3">
      {Object.entries(scores).map(([key, value]) => {
        const pct = Math.min(100, Math.max(0, (value / 10) * 100));
        const color = dimensionColors[key] || '#6b7280';
        return (
          <div key={key}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-400 capitalize">
                {key.replace(/_/g, ' ')}
              </span>
              <span className="text-gray-300 font-mono">{value}/10</span>
            </div>
            <div className="w-full h-2 rounded-full bg-[#2a2a2a]">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
