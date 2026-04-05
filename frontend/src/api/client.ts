class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `/api${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(body || res.statusText, res.status);
  }

  return res.json();
}

export const api = {
  getStatus: () => request<import('./types').DashboardData>('/status'),

  getChannels: () => request<import('./types').Channel[]>('/channels'),

  getChannel: (id: number) => request<import('./types').Channel>(`/channels/${id}`),

  getRuns: (params?: { channel_id?: number; status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.channel_id) search.set('channel_id', String(params.channel_id));
    if (params?.status) search.set('status', params.status);
    if (params?.limit) search.set('limit', String(params.limit));
    const qs = search.toString();
    return request<import('./types').RunSummary[]>(`/runs${qs ? `?${qs}` : ''}`);
  },

  getRun: (id: number) => request<import('./types').RunDetail>(`/runs/${id}`),

  publishRun: ({ id, privacy }: { id: number; privacy?: string }) =>
    request<{ status: string }>(`/runs/${id}/publish`, {
      method: 'POST',
      body: JSON.stringify({ privacy: privacy || 'private' }),
    }),

  rejectRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}/reject`, { method: 'POST' }),

  deleteRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}`, { method: 'DELETE' }),

  cancelRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}/cancel`, { method: 'POST' }),

  getRunMetrics: (runId: number) =>
    request<import('./types').VideoMetrics>(`/metrics/${runId}`),

  getChannelMetrics: (channelId: number) =>
    request<import('./types').ChannelMetrics>(`/metrics/channel/${channelId}`),

  getConcepts: (status: string = 'pending') => {
    const qs = status ? `?status=${status}` : '';
    return request<unknown[]>(`/concepts${qs}`);
  },

  approveConcept: (id: number) =>
    request<{ id: number; status: string }>(`/concepts/${id}/approve`, { method: 'POST' }),

  approveArt: ({ id, engine }: { id: number; engine: string }) =>
    request<{ run_id: number; workflow_id: string }>(`/concepts/${id}/approve-art?engine=${engine}`, { method: 'POST' }),

  rejectConcept: (id: number) =>
    request<{ status: string }>(`/concepts/${id}/reject`, { method: 'POST' }),

  // Content Bank
  getContentBank: (params?: { channel_id?: number; status?: string }) => {
    const search = new URLSearchParams();
    if (params?.channel_id) search.set('channel_id', String(params.channel_id));
    if (params?.status) search.set('status', params.status || 'all');
    const qs = search.toString();
    return request<import('./types').ContentBankItem[]>(`/content-bank${qs ? `?${qs}` : ''}`);
  },

  addToContentBank: (item: { channel_id: number; title: string; concept_json: unknown; priority?: number }) =>
    request<{ id: number }>('/content-bank', { method: 'POST', body: JSON.stringify(item) }),

  bulkAddToContentBank: (payload: { channel_id: number; concepts: unknown[] }) =>
    request<{ added: number; ids: number[] }>('/content-bank/bulk', { method: 'POST', body: JSON.stringify(payload) }),

  deleteContentBankItem: (id: number) =>
    request<{ deleted: boolean }>(`/content-bank/${id}`, { method: 'DELETE' }),

  generateNow: (id: number) =>
    request<{ id: number }>(`/content-bank/${id}/generate-now`, { method: 'POST' }),

  // Concept Drafts
  getConceptDrafts: (params?: { status?: string; channel_id?: number; form_type?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set('status', params.status);
    if (params?.channel_id) search.set('channel_id', String(params.channel_id));
    if (params?.form_type) search.set('form_type', params.form_type);
    const qs = search.toString();
    return request<import('./types').ConceptDraft[]>(`/concept-drafts${qs ? `?${qs}` : ''}`);
  },

  getConceptDraftsSummary: () =>
    request<import('./types').ConceptDraftSummary[]>('/concept-drafts/summary'),

  approveConceptDraft: (id: number) =>
    request<{ draft_id: number; content_bank_id: number }>(`/concept-drafts/${id}/approve`, { method: 'POST' }),

  rejectConceptDraft: (id: number) =>
    request<{ draft_id: number }>(`/concept-drafts/${id}/reject`, { method: 'POST' }),

  generateConceptDrafts: (channel_id: number, count: number = 5) =>
    request<{ generated: number }>(`/concept-drafts/generate?channel_id=${channel_id}&count=${count}`, { method: 'POST' }),

  // Scheduling
  getSchedules: () => request<import('./types').ChannelSchedule[]>('/schedules'),

  getSchedule: (channelId: number) =>
    request<import('./types').ChannelSchedule>(`/schedules/${channelId}`),

  updateSchedule: (channelId: number, config: Partial<import('./types').ChannelSchedule>) =>
    request<{ updated: boolean }>(`/schedules/${channelId}`, { method: 'PUT', body: JSON.stringify(config) }),

  pauseChannel: (channelId: number) =>
    request<{ paused: boolean }>(`/schedules/${channelId}/pause`, { method: 'POST' }),

  resumeChannel: (channelId: number) =>
    request<{ paused: boolean }>(`/schedules/${channelId}/resume`, { method: 'POST' }),
};

export { ApiError };
