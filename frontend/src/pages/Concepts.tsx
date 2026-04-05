import { useState } from 'react';
import { useConceptDrafts, useApproveConceptDraft, useRejectConceptDraft } from '../hooks/useApi';
import type { ConceptDraft } from '../api/types';

export default function Concepts() {
  const [formType, setFormType] = useState<'short' | 'long'>('short');
  const { data: drafts, isLoading } = useConceptDrafts({ status: 'pending', form_type: formType });
  const approveMutation = useApproveConceptDraft();
  const rejectMutation = useRejectConceptDraft();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 bg-[#1a1a1a] rounded" />
        {[1, 2, 3].map((i) => <div key={i} className="h-40 bg-[#1a1a1a] rounded-lg" />)}
      </div>
    );
  }

  // Group drafts by channel, excluding dismissed
  const byChannel = new Map<number, { name: string; drafts: ConceptDraft[] }>();
  for (const d of (drafts || []).filter(d => !dismissed.has(d.id))) {
    if (!byChannel.has(d.channel_id)) {
      byChannel.set(d.channel_id, { name: d.channel_name, drafts: [] });
    }
    byChannel.get(d.channel_id)!.drafts.push(d);
  }

  const channels = Array.from(byChannel.entries()).sort((a, b) => a[1].name.localeCompare(b[1].name));

  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-semibold text-white">Concepts</h1>
          <div className="flex rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] overflow-hidden">
            <button
              onClick={() => { setFormType('short'); setDismissed(new Set()); }}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${formType === 'short' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              Shorts
            </button>
            <button
              onClick={() => { setFormType('long'); setDismissed(new Set()); }}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${formType === 'long' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              Long Form
            </button>
          </div>
        </div>
        <p className="text-gray-500 text-sm mt-1">
          {drafts?.length || 0} concepts across {channels.length} channels
        </p>
      </div>

      {channels.length === 0 && (
        <div className="p-8 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-center">
          <p className="text-gray-400">No pending concepts. The worker will generate them automatically.</p>
        </div>
      )}

      {channels.map(([channelId, { name, drafts: channelDrafts }]) => (
        <section key={channelId}>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-sm font-medium text-green-400 uppercase tracking-wider">{name}</h2>
            <span className="text-gray-600 text-xs">{channelDrafts.length}/5</span>
          </div>
          <div className="space-y-2">
            {channelDrafts.map((draft) => (
              <ConceptCard
                key={draft.id}
                draft={draft}
                expanded={expanded === draft.id}
                onToggle={() => setExpanded(expanded === draft.id ? null : draft.id)}
                onApprove={() => {
                  setDismissed(s => new Set(s).add(draft.id));
                  approveMutation.mutate(draft.id);
                }}
                onReject={() => {
                  setDismissed(s => new Set(s).add(draft.id));
                  rejectMutation.mutate(draft.id);
                }}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function ConceptCard({
  draft, expanded, onToggle, onApprove, onReject,
}: {
  draft: ConceptDraft;
  expanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const concept = draft.concept || {};
  const beats = concept.beats || [];
  const narration = concept.narration || [];
  const chapters = concept.chapters || [];
  const isLongForm = concept.long_form || concept.format_version === 2 && narration.length >= 20;
  const grokCount = beats.filter((b: { type: string }) => b.type === 'grok').length;
  const imageCount = beats.filter((b: { type: string }) => b.type === 'image').length;

  // Estimate duration from word count (150 words/min speaking pace)
  const totalWords = narration.reduce((sum: number, line: string) => sum + line.split(/\s+/).length, 0);
  const estimatedDuration = isLongForm
    ? Math.round(totalWords / 150)
    : Math.round((narration.length || beats.length) * 4);

  return (
    <div className="rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] overflow-hidden">
      {/* Header row */}
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <button onClick={onToggle} className="flex-1 text-left min-w-0">
            <div className="flex items-center gap-2">
              {isLongForm && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-purple-500/15 text-purple-400 shrink-0">
                  LONG
                </span>
              )}
              <h3 className="text-white font-medium text-sm">{draft.title}</h3>
              <svg className={`w-4 h-4 text-gray-500 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
                   fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            {draft.brief && (
              <p className="text-gray-500 text-xs mt-1">{draft.brief}</p>
            )}
          </button>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={onApprove}
              className="px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-xs font-medium transition-colors"
            >
              Approve
            </button>
            <button
              onClick={onReject}
              className="px-3 py-1.5 rounded bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-400 text-xs font-medium transition-colors"
            >
              Reject
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {isLongForm ? (
            <>
              <span>{narration.length} lines</span>
              <span>{chapters.length} chapters</span>
              <span>~{estimatedDuration} min</span>
            </>
          ) : (
            <>
              <span>{narration.length || beats.length} {narration.length ? 'lines' : 'beats'}</span>
              {grokCount > 0 && <span className="text-purple-400">{grokCount} video</span>}
              {imageCount > 0 && <span className="text-blue-400">{imageCount} img</span>}
              {narration.length > 0 && <span>~{estimatedDuration}s</span>}
            </>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-[#2a2a2a] p-4 space-y-3">
          {/* Tags */}
          {concept.tags && concept.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {concept.tags.map((tag: string, i: number) => (
                <span key={i} className="px-2 py-0.5 rounded bg-[#2a2a2a] text-gray-400 text-[10px]">{tag}</span>
              ))}
            </div>
          )}

          {/* Thumbnail spec for long-form */}
          {isLongForm && concept.thumbnail && (
            <div className="p-3 rounded bg-[#0f0f0f] space-y-1">
              <h4 className="text-orange-400 text-xs font-bold uppercase tracking-wider">Thumbnail</h4>
              <p className="text-gray-200 text-xs"><span className="text-gray-500">Visual:</span> {concept.thumbnail.visual}</p>
              {concept.thumbnail.text && (
                <p className="text-gray-200 text-xs"><span className="text-gray-500">Text:</span> {concept.thumbnail.text}</p>
              )}
              {concept.thumbnail.emotion && (
                <p className="text-gray-200 text-xs"><span className="text-gray-500">Emotion:</span> {concept.thumbnail.emotion}</p>
              )}
            </div>
          )}

          {/* Caption */}
          {concept.caption && (
            <p className="text-gray-400 text-xs italic">"{concept.caption}"</p>
          )}

          {/* Chapter structure for long-form */}
          {isLongForm && chapters.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-purple-400 text-xs font-bold uppercase tracking-wider">Chapters</h4>
              {chapters.map((ch: { title: string; timing: string; purpose: string }, i: number) => (
                <div key={i} className="flex gap-2 p-2 rounded bg-[#0f0f0f]">
                  <span className="text-gray-600 text-[10px] font-mono shrink-0 pt-0.5">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-white text-xs font-medium">{ch.title}</span>
                      <span className="text-gray-600 text-[10px]">{ch.timing}</span>
                    </div>
                    <p className="text-gray-500 text-[11px]">{ch.purpose}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Open loops for long-form */}
          {isLongForm && concept.open_loops && concept.open_loops.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-yellow-400 text-xs font-bold uppercase tracking-wider">Open Loops</h4>
              {concept.open_loops.map((loop: string, i: number) => (
                <p key={i} className="text-gray-400 text-xs pl-2 border-l border-yellow-500/30">{loop}</p>
              ))}
            </div>
          )}

          {/* Narration lines (format_version 2) */}
          {narration.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-green-400 text-xs font-bold uppercase tracking-wider">
                Narration ({narration.length} lines)
              </h4>
              {narration.map((line: string, i: number) => (
                <div key={i} className="flex gap-2 p-2 rounded bg-[#0f0f0f]">
                  <span className="text-gray-600 text-[10px] font-mono shrink-0">{i}</span>
                  <p className="text-gray-200 text-sm">"{line}"</p>
                </div>
              ))}
            </div>
          )}

          {/* Legacy beats */}
          {beats.length > 0 && narration.length === 0 && beats.map((beat: { type: string; label?: string; narration: string; video_prompt?: string; image?: string }, i: number) => (
            <div key={i} className="flex gap-3 p-3 rounded bg-[#0f0f0f]">
              <div className="shrink-0 flex flex-col items-center gap-1">
                <span className="text-gray-600 text-[10px] font-mono">{i}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                  beat.type === 'grok' ? 'bg-purple-500/15 text-purple-400'
                  : beat.type === 'video' ? 'bg-orange-500/15 text-orange-400'
                  : beat.type === 'veo' ? 'bg-cyan-500/15 text-cyan-400'
                  : 'bg-blue-500/15 text-blue-400'
                }`}>
                  {beat.type}
                </span>
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                {beat.label && (
                  <span className="text-yellow-400 text-xs font-bold">[{beat.label}]</span>
                )}
                <p className="text-gray-200 text-sm">"{beat.narration}"</p>
                {beat.video_prompt && (
                  <p className="text-purple-300/60 text-[11px] truncate">Video: {beat.video_prompt}</p>
                )}
                {beat.image && <p className="text-blue-300/40 text-[11px] truncate">Img: {beat.image}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
