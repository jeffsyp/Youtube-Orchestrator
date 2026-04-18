export interface ChannelStats {
  published: number;
  completed: number;
  failed: number;
  total: number;
}

export interface Channel {
  id: number;
  name: string;
  niche: string;
  pipeline: string;
  description: string;
  stats: ChannelStats;
}

export interface RunSummary {
  id: number;
  channel_id: number;
  channel_name: string;
  status: string;
  current_step: string | null;
  started_at: string;
  completed_at: string | null;
  error: string | null;
  title: string | null;
  review_score: number | null;
  review_recommendation: string | null;
  production_qa_verdict: string | null;
  video_path: string | null;
  thumbnail_path: string | null;
  content_type: string;
  elapsed_seconds: number | null;
  stalled: boolean;
  youtube_url: string | null;
  youtube_privacy: string | null;
  last_change?: string | null;
}

export interface RunDetail extends RunSummary {
  assets: Array<{ id: number; asset_type: string; content: string | null }>;
}

export interface SystemCheck {
  name: string;
  active: boolean;
}

export interface TodayChannelStats {
  name: string;
  id: number;
  published: number;
  ready: number;
  failed: number;
  total: number;
}

export interface TodayUpload {
  channel: string;
  url?: string;
  video_id?: string;
  title?: string;
  publish_at?: string;
}

export interface TodayStats {
  published: number;
  ready: number;
  generating: number;
  failed: number;
  total: number;
  channels_active: number;
  by_channel: TodayChannelStats[];
  uploads: TodayUpload[];
}

export interface DashboardData {
  running_pipelines: RunSummary[];
  recent_runs: RunSummary[];
  channel_stats: Channel[];
  system_checks: SystemCheck[];
  today_stats: TodayStats;
}

export interface VideoMetrics {
  run_id: number;
  video_id: string;
  title: string | null;
  views: number;
  likes: number;
  comments: number;
  youtube_url: string | null;
  privacy: string | null;
  published_at: string | null;
}

export interface ChannelMetrics {
  channel_id: number;
  channel_name: string;
  total_views: number;
  total_likes: number;
  total_comments: number;
  video_count: number;
  avg_views_per_video: number;
}

export interface ContentBankItem {
  id: number;
  channel_id: number;
  channel_name: string;
  title: string;
  status: string;
  priority: number;
  created_at: string | null;
  run_id: number | null;
  error: string | null;
  attempt_count: number;
  concept_id?: number | null;
}

export interface ConceptThumbnail {
  visual?: string;
  text?: string;
  emotion?: string;
}

export interface ConceptChapter {
  title: string;
  timing?: string;
  purpose?: string;
}

export interface ConceptBeat {
  narration?: string;
  image?: string;
  type?: string;
  video_prompt?: string;
  label?: string;
}

export interface ConceptData {
  beats?: ConceptBeat[];
  narration?: string[];
  chapters?: ConceptChapter[];
  long_form?: boolean;
  format_version?: number;
  thumbnail?: ConceptThumbnail;
  open_loops?: string[];
  voice_id?: string;
  caption?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ConceptDraft {
  id: number;
  channel_id: number;
  channel_name: string;
  title: string;
  brief: string | null;
  score: number;
  status: string;
  concept: ConceptData;
  created_at: string | null;
  form_type: string;
}

export interface ReviewTask {
  id: number;
  run_id: number;
  concept_id: number | null;
  channel_id: number | null;
  kind: string;
  status: string;
  payload: Record<string, unknown>;
  resolution: Record<string, unknown>;
  created_at: string | null;
  resolved_at?: string | null;
  current_step?: string | null;
  run_status?: string | null;
  channel_name?: string | null;
  title?: string | null;
}

export interface RunEvent {
  id: number;
  run_id: number;
  ts: string | null;
  level: string;
  event_type: string;
  stage: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface RunImagesResponse {
  run_id: number;
  images: Array<{ name: string; b64: string; narration?: string }>;
  total: number;
  expected: number;
  review_task_id?: number | null;
}

export interface ConceptDraftSummary {
  channel_id: number;
  channel_name: string;
  pending_count: number;
  total_approved: number;
  total_rejected: number;
}

export interface ChannelSchedule {
  channel_id: number;
  channel_name: string;
  videos_per_day: number;
  time_windows: Array<{ start: string; end: string }>;
  auto_upload: boolean;
  upload_privacy: string;
  paused: boolean;
  timezone: string;
  voice_id: string;
  queue_depth: number;
  today_count: number;
}
