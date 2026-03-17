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
  review_score: number | null;
  review_recommendation: string | null;
  video_path: string | null;
  thumbnail_path: string | null;
  content_type: string;
  elapsed_seconds: number | null;
  youtube_url: string | null;
  youtube_privacy: string | null;
}

export interface Idea {
  id: number;
  title: string;
  hook: string;
  angle: string;
  score: number | null;
}

export interface RunDetail extends RunSummary {
  ideas: Idea[];
  review: Record<string, unknown> | null;
}

export interface SystemCheck {
  name: string;
  active: boolean;
}

export interface DashboardData {
  running_pipelines: RunSummary[];
  recent_runs: RunSummary[];
  channel_stats: Channel[];
  system_checks: SystemCheck[];
}

export interface BatchRunRequest {
  channel_ids: number[];
  privacy?: string;
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
