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

  startBatchRuns: (data: import('./types').BatchRunRequest) =>
    request<{ started: number[] }>('/runs/batch', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  publishRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}/publish`, { method: 'POST' }),

  deleteRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}`, { method: 'DELETE' }),

  rejectRun: (id: number) =>
    request<{ status: string }>(`/runs/${id}/reject`, { method: 'POST' }),

  getRunMetrics: (runId: number) =>
    request<import('./types').VideoMetrics>(`/metrics/${runId}`),

  getChannelMetrics: (channelId: number) =>
    request<import('./types').ChannelMetrics>(`/metrics/channel/${channelId}`),
};

export { ApiError };
