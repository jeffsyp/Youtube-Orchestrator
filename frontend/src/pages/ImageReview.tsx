import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

interface RunImage {
  name: string;
  b64: string;
  narration?: string;
}

interface RunWithImages {
  run_id: number;
  channel_name: string;
  title: string;
  current_step: string;
  images: RunImage[];
}

export default function ImageReview() {
  // Fetch all runs that have images
  const { data: runs } = useQuery<any[]>({
    queryKey: ['runs-with-images'],
    queryFn: async () => {
      // Get all running + pending_review runs
      const res = await fetch('/api/runs?limit=20');
      const allRuns = await res.json();

      // For each, try to fetch images
      const withImages: RunWithImages[] = [];
      for (const run of allRuns) {
        if (!['running', 'pending_review'].includes(run.status)) continue;
        // Only show runs that are in the image generation/review stage
        const step = run.current_step || '';
        const imageSteps = ['generating scene images', 'images ready for review', 'generating style anchor',
                           'planning sub-actions', 'creating scene variants', 'regenerating images'];
        if (run.status === 'running' && !imageSteps.some(s => step.startsWith(s))) continue;
        try {
          const imgRes = await fetch(`/api/runs/${run.id}/images`);
          if (imgRes.ok) {
            const imgData = await imgRes.json();
            if (imgData.images?.length > 0) {
              withImages.push({
                run_id: run.id,
                channel_name: run.channel_name,
                title: run.title || '(untitled)',
                current_step: run.current_step || '',
                images: imgData.images,
              });
            }
          }
        } catch {}
      }
      return withImages;
    },
    refetchInterval: 10000,
  });

  if (!runs || runs.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-semibold text-white mb-6">Image Review</h2>
        <p className="text-gray-500">No runs with images to review.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-white mb-6">Image Review</h2>
      <div className="space-y-8">
        {runs.map((run) => (
          <RunImageReview key={run.run_id} run={run} />
        ))}
      </div>
    </div>
  );
}

function RunImageReview({ run }: { run: RunWithImages }) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [denied, setDenied] = useState<Set<string>>(new Set());
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const toggleDeny = (name: string) => {
    const next = new Set(denied);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setDenied(next);
  };

  const approveAll = async () => {
    setSubmitting(true);
    await fetch(`/api/runs/${run.run_id}/images/approve-all`, { method: 'POST' });
    setSubmitting(false);
  };

  const submitReview = async () => {
    setSubmitting(true);
    const globalFeedback = feedback['__global'] || '';
    const deniedList = Array.from(denied).map(name => ({
      name,
      feedback: feedback[name] || globalFeedback || 'Regenerate this image',
    }));
    const approvedList = run.images.filter(img => !denied.has(img.name)).map(img => img.name);
    await fetch(`/api/runs/${run.run_id}/images/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: approvedList, denied: deniedList }),
    });
    setSubmitting(false);
    setDenied(new Set());
    setFeedback({});
  };

  return (
    <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Link to={`/runs/${run.run_id}`} className="text-blue-400 text-xs no-underline hover:text-blue-300">
              #{run.run_id}
            </Link>
            <span className="text-gray-500 text-xs">{run.channel_name}</span>
            <span className="text-white text-sm font-medium">{run.title}</span>
          </div>
          <div className="flex items-center gap-3 mt-1">
            {run.current_step === 'images ready for review' ? (
              <span className="text-green-400 text-xs font-bold">ALL IMAGES READY — waiting for your approval</span>
            ) : run.current_step === 'generating scene images' ? (
              <span className="text-yellow-400 text-xs font-mono animate-pulse">Generating images...</span>
            ) : (
              <span className="text-yellow-400 text-xs font-mono">{run.current_step}</span>
            )}
            <span className="text-gray-500 text-xs">{run.images.length} images</span>
            {run.expected_images && run.expected_images > run.images.length && (
              <>
                <div className="flex-1 max-w-[200px] h-1.5 bg-[#333] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all duration-500"
                    style={{ width: `${(run.images.length / run.expected_images) * 100}%` }}
                  />
                </div>
                <span className="text-purple-400 text-xs font-mono">{run.images.length}/{run.expected_images}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {denied.size > 0 && (
            <button
              onClick={submitReview}
              disabled={submitting}
              className="px-4 py-2 text-sm rounded bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
            >
              {submitting ? '...' : `Deny ${denied.size} & Regenerate`}
            </button>
          )}
          <button
            onClick={() => { setDenied(new Set(run.images.map(i => i.name))); }}
            className="px-4 py-2 text-sm rounded bg-yellow-600 hover:bg-yellow-500 text-white"
          >
            Deny All
          </button>
          <button
            onClick={approveAll}
            disabled={submitting}
            className="px-4 py-2 text-sm rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
          >
            {submitting ? '...' : 'Approve All'}
          </button>
        </div>
      </div>

      {/* Image Grid */}
      <div className="grid grid-cols-4 gap-3">
        {run.images.map((img) => (
          <div
            key={img.name}
            className={`relative rounded-lg border-2 transition-all ${
              denied.has(img.name)
                ? 'border-red-500'
                : 'border-transparent hover:border-[#444]'
            }`}
          >
            <img
              src={`data:image/png;base64,${img.b64}`}
              alt={img.name}
              className="w-full rounded-lg"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-black/80 px-2 py-2 rounded-b-lg">
              {img.narration && (
                <p className="text-[10px] text-gray-200 mb-1 leading-tight">{img.narration}</p>
              )}
              <div className="flex items-center justify-between">
              <span className="text-[10px] text-gray-500 font-mono">{img.name}</span>
              <button
                onClick={() => toggleDeny(img.name)}
                className={`px-2 py-0.5 text-[10px] rounded font-bold ${
                  denied.has(img.name)
                    ? 'bg-green-600 text-white hover:bg-green-500'
                    : 'bg-red-600 text-white hover:bg-red-500'
                }`}
              >
                {denied.has(img.name) ? 'Undo' : 'Deny'}
              </button>
              </div>
            </div>
            {denied.has(img.name) && (
              <>
                <div className="absolute inset-0 flex items-center justify-center bg-red-900/40 rounded-lg pointer-events-none">
                  <span className="text-red-300 font-bold text-lg">DENIED</span>
                </div>
                <div className="mt-1">
                  <input
                    type="text"
                    placeholder="What should change?"
                    value={feedback[img.name] || ''}
                    onChange={(e) => setFeedback(prev => ({ ...prev, [img.name]: e.target.value }))}
                    className="w-full px-2 py-1 text-xs bg-[#111] border border-red-500 rounded text-gray-200 placeholder-gray-500 focus:outline-none"
                  />
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {/* Feedback for denied images */}
      {denied.size > 0 && (
        <div className="mt-4 space-y-3 p-4 bg-[#111] rounded-lg">
          {/* Global feedback — applies to all denied */}
          <div>
            <p className="text-xs text-gray-400 mb-1">Global feedback (applies to all denied):</p>
            <input
              type="text"
              placeholder="e.g. Make the pool an olympic pool with lane dividers, viewed from behind the starting blocks"
              value={feedback['__global'] || ''}
              onChange={(e) => setFeedback(prev => ({ ...prev, '__global': e.target.value }))}
              onClick={(e) => e.stopPropagation()}
              className="w-full px-3 py-2 text-sm bg-[#1a1a1a] border border-[#333] rounded text-gray-200 placeholder-gray-600 focus:border-blue-500 outline-none"
            />
          </div>
          {/* Per-image feedback */}
          <div>
            <p className="text-xs text-gray-400 mb-1">Per-image feedback (optional, overrides global):</p>
            {Array.from(denied).map(name => (
              <div key={name} className="flex gap-2 items-center mt-1">
                <span className="text-xs text-red-400 font-mono w-36 shrink-0">{name}</span>
                <input
                  type="text"
                  placeholder="Specific fix for this image..."
                  value={feedback[name] || ''}
                  onChange={(e) => setFeedback(prev => ({ ...prev, [name]: e.target.value }))}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 px-3 py-1.5 text-sm bg-[#1a1a1a] border border-[#333] rounded text-gray-200 placeholder-gray-600 focus:border-blue-500 outline-none"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
