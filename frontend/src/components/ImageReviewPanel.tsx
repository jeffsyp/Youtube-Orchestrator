import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiError } from '../api/client';
import type { RunImagesResponse } from '../api/types';

interface ImageReviewPanelProps {
  runId: number;
  currentStep?: string | null;
  title?: string | null;
  channelName?: string | null;
  showRunHeader?: boolean;
}

export default function ImageReviewPanel({
  runId,
  currentStep,
  title,
  channelName,
  showRunHeader = false,
}: ImageReviewPanelProps) {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [denied, setDenied] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  const { data, isLoading, isError, error } = useQuery<RunImagesResponse>({
    queryKey: ['run-images', runId],
    queryFn: () => api.getRunImages(runId),
    refetchInterval: currentStep === 'images ready for review' || currentStep === 'regenerating images' ? 3000 : false,
  });

  const images = data?.images || [];
  if (!isLoading && !isError && images.length === 0) return null;

  const toggleDeny = (name: string) => {
    const next = new Set(denied);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setDenied(next);
  };

  const denyAll = () => {
    setDenied(new Set(images.map((img) => img.name)));
  };

  const clearDenied = () => {
    setDenied(new Set());
    setFeedback({});
  };

  const approveAll = async () => {
    setSubmitting(true);
    try {
      await api.approveAllImages(runId);
      queryClient.invalidateQueries({ queryKey: ['review-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      queryClient.invalidateQueries({ queryKey: ['run-images', runId] });
    } finally {
      setSubmitting(false);
    }
  };

  const submitReview = async () => {
    setSubmitting(true);
    try {
      const globalFeedback = feedback.__global || '';
      const deniedList = Array.from(denied).map((name) => ({
        name,
        feedback: feedback[name] || globalFeedback || 'Regenerate this image',
      }));
      const approvedList = images.filter((img) => !denied.has(img.name)).map((img) => img.name);
      await api.approveRunImages(runId, { approved: approvedList, denied: deniedList });
      setDenied(new Set());
      setFeedback({});
      queryClient.invalidateQueries({ queryKey: ['review-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      queryClient.invalidateQueries({ queryKey: ['run-images', runId] });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <div className="flex items-center justify-between mb-4 gap-4">
        <div>
          {showRunHeader ? (
            <>
              <div className="flex items-center gap-2">
                <Link to={`/runs/${runId}`} className="text-blue-400 text-xs no-underline hover:text-blue-300">
                  #{runId}
                </Link>
                {channelName && <span className="text-gray-500 text-xs">{channelName}</span>}
                <span className="text-white text-sm font-medium">{title || 'Untitled'}</span>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-yellow-400 text-xs font-mono">{currentStep || 'review'}</span>
                <span className="text-gray-500 text-xs">{images.length} images</span>
                {!!data?.expected && data.expected > images.length && (
                  <>
                    <div className="flex-1 max-w-[180px] h-1.5 bg-[#333] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full transition-all duration-500"
                        style={{ width: `${(images.length / data.expected) * 100}%` }}
                      />
                    </div>
                    <span className="text-green-400 text-xs font-mono">{images.length}/{data.expected}</span>
                  </>
                )}
              </div>
            </>
          ) : (
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
              Scene Images ({images.length})
            </h3>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={denyAll}
            disabled={submitting || images.length === 0 || denied.size === images.length}
            className="px-3 py-1 text-xs rounded bg-orange-600 hover:bg-orange-500 text-white disabled:opacity-50 disabled:hover:bg-orange-600"
          >
            Deny All
          </button>
          <button
            onClick={clearDenied}
            disabled={submitting || denied.size === 0}
            className="px-3 py-1 text-xs rounded bg-[#333] hover:bg-[#444] text-white disabled:opacity-50 disabled:hover:bg-[#333]"
          >
            Clear Denials
          </button>
          <button
            onClick={submitReview}
            disabled={submitting || denied.size === 0}
            className="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-500 text-white disabled:opacity-50 disabled:hover:bg-red-600"
          >
            {submitting && denied.size > 0 ? '...' : denied.size > 0 ? `Deny ${denied.size}` : 'Deny Selected'}
          </button>
          <button
            onClick={approveAll}
            disabled={submitting}
            className="px-3 py-1 text-xs rounded bg-green-600 hover:bg-green-500 text-white disabled:opacity-50"
          >
            {submitting ? '...' : 'Approve All'}
          </button>
        </div>
      </div>

      {isError && (
        <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2">
          <p className="text-xs text-yellow-300">
            Image refresh failed{error instanceof ApiError ? ` (${error.status})` : ''}. Keeping the last successful image set visible.
          </p>
        </div>
      )}

      {isLoading && images.length === 0 && (
        <div className="rounded-lg border border-[#333] bg-[#111] px-3 py-6 text-center text-sm text-gray-500">
          Loading scene images...
        </div>
      )}

      {!isLoading && images.length === 0 && isError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-6 text-center text-sm text-red-300">
          The image review payload failed to load.
        </div>
      )}

      {images.length > 0 && (
        <div className={`${showRunHeader ? 'grid grid-cols-4' : 'grid grid-cols-3'} gap-3`}>
        {images.map((img) => (
          <div
            key={img.name}
            className={`relative rounded-lg border-2 transition-all ${
              denied.has(img.name) ? 'border-red-500' : 'border-transparent hover:border-[#444]'
            }`}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => toggleDeny(img.name)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleDeny(img.name);
                }
              }}
              className="block w-full text-left bg-transparent border-0 p-0 cursor-pointer"
            >
              <img
                src={`data:image/png;base64,${img.b64}`}
                alt={img.name}
                className="w-full rounded-lg"
              />
              <div className="absolute top-2 right-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleDeny(img.name);
                  }}
                  className={`px-3 py-1.5 text-xs rounded-md font-semibold shadow-md ${
                    denied.has(img.name) ? 'bg-green-600 hover:bg-green-500 text-white' : 'bg-red-600 hover:bg-red-500 text-white'
                  }`}
                >
                  {denied.has(img.name) ? 'Undo Deny' : 'Deny'}
                </button>
              </div>
              <div className="absolute bottom-0 left-0 right-0 bg-black/80 px-2 py-2 rounded-b-lg">
                {img.narration && (
                  <p className="text-[10px] text-gray-200 mb-1 leading-tight">{img.narration}</p>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-gray-500 font-mono">{img.name}</span>
                  <span className={`px-2 py-0.5 text-[10px] rounded font-bold ${
                    denied.has(img.name) ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
                  }`}>
                    {denied.has(img.name) ? 'Denied' : 'Click To Deny'}
                  </span>
                </div>
              </div>
            </div>
            {denied.has(img.name) && (
              <div className="mt-1">
                <input
                  type="text"
                  placeholder="What should change?"
                  value={feedback[img.name] || ''}
                  onChange={(e) => setFeedback((prev) => ({ ...prev, [img.name]: e.target.value }))}
                  className="w-full px-2 py-1 text-xs bg-[#111] border border-red-500 rounded text-gray-200 placeholder-gray-500 focus:outline-none"
                />
              </div>
            )}
          </div>
        ))}
        </div>
      )}

      {denied.size > 0 && (
        <div className="mt-4">
          <input
            type="text"
            placeholder="Global feedback for all denied images"
            value={feedback.__global || ''}
            onChange={(e) => setFeedback((prev) => ({ ...prev, __global: e.target.value }))}
            className="w-full px-3 py-2 text-sm bg-[#111] border border-[#333] rounded text-gray-200 placeholder-gray-500 focus:outline-none"
          />
        </div>
      )}
    </div>
  );
}
