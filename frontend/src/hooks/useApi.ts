import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 5000,
  });
}

export function useChannels() {
  return useQuery({
    queryKey: ['channels'],
    queryFn: api.getChannels,
  });
}

export function useChannel(id: number) {
  return useQuery({
    queryKey: ['channels', id],
    queryFn: () => api.getChannel(id),
    enabled: id > 0,
  });
}

export function useRuns(filters?: { channel_id?: number; status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['runs', filters],
    queryFn: () => api.getRuns(filters),
    refetchInterval: 10000,
  });
}

export function useRunDetail(id: number) {
  return useQuery({
    queryKey: ['runs', id],
    queryFn: () => api.getRun(id),
    enabled: id > 0,
    refetchInterval: 10000,
  });
}

export function useRunMetrics(runId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['metrics', 'run', runId],
    queryFn: () => api.getRunMetrics(runId),
    enabled: enabled && runId > 0,
    refetchInterval: 60000,
    retry: false,
  });
}

export function useChannelMetrics(channelId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['metrics', 'channel', channelId],
    queryFn: () => api.getChannelMetrics(channelId),
    enabled: enabled && channelId > 0,
    refetchInterval: 60000,
    retry: false,
  });
}

export function usePublishRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { id: number; privacy?: string }) => api.publishRun(args),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function useRejectRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.rejectRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.cancelRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function useDeleteRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteRun,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function useConceptDrafts(params?: { status?: string; channel_id?: number; form_type?: string }) {
  return useQuery({
    queryKey: ['concept-drafts', params],
    queryFn: () => api.getConceptDrafts(params),
    refetchInterval: 10000,
  });
}

export function useConceptDraftsSummary() {
  return useQuery({
    queryKey: ['concept-drafts-summary'],
    queryFn: api.getConceptDraftsSummary,
    refetchInterval: 10000,
  });
}

export function useApproveConceptDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.approveConceptDraft,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['concept-drafts'] });
      qc.invalidateQueries({ queryKey: ['concept-drafts-summary'] });
      qc.invalidateQueries({ queryKey: ['content-bank'] });
    },
  });
}

export function useRejectConceptDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.rejectConceptDraft,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['concept-drafts'] });
      qc.invalidateQueries({ queryKey: ['concept-drafts-summary'] });
    },
  });
}

export function useContentBank(params?: { channel_id?: number; status?: string }) {
  return useQuery({
    queryKey: ['content-bank', params],
    queryFn: () => api.getContentBank(params),
    refetchInterval: 10000,
  });
}

export function useSchedules() {
  return useQuery({
    queryKey: ['schedules'],
    queryFn: api.getSchedules,
    refetchInterval: 10000,
  });
}

export function useSchedule(channelId: number) {
  return useQuery({
    queryKey: ['schedules', channelId],
    queryFn: () => api.getSchedule(channelId),
    enabled: channelId > 0,
  });
}

export function useGenerateNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.generateNow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['content-bank'] });
    },
  });
}

export function usePauseChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.pauseChannel,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] });
    },
  });
}

export function useResumeChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.resumeChannel,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedules'] });
    },
  });
}
