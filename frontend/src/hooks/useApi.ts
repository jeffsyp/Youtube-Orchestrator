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

export function useStartBatchRuns() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.startBatchRuns,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['status'] });
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}

export function usePublishRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.publishRun,
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
