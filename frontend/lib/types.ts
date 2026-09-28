export type Metric = {
  value: number | null;
  available: boolean;
  source: string | null;
  note: string | null;
};

export type Creator = {
  id: number;
  username: string;
  display_name: string | null;
  profile_url: string;
  profile_picture_url: string | null;
  bio: string | null;
  is_verified: boolean | null;
  status: "new" | "saved" | "ignored";
  followers: Metric;
  posts_7d: Metric;
  posts_30d: Metric;
  posts_90d: Metric;
  last_post_at: string | null;
  profile_likes: Metric;
  profile_replies: Metric;
  profile_reposts: Metric;
  profile_quotes: Metric;
  profile_views: Metric;
  creator_signal: "none" | "low" | "medium" | "high" | null;
  monetization_signal: "none" | "possible" | null;
  monetization_label: string | null;
  signal_terms: string[];
};

export type Post = {
  id: number;
  threads_post_id: string;
  text: string | null;
  permalink: string | null;
  timestamp: string | null;
  media_type: string | null;
  media_url: string | null;
};

export type Result = {
  id: number;
  creator: Creator;
  latest_post: Post | null;
  best_image_url: string | null;
  visual_similarity: number | null;
  best_image_similarity: number | null;
  top_k_avg_similarity: number | null;
  images_analyzed: number;
  activity_score: number | null;
  engagement_score: number | null;
  creator_signal_score: number | null;
  keyword_relevance: number | null;
  audience_score: number | null;
  total_score: number;
  score_breakdown: {
    effective_weights: Record<string, number>;
    contributions: Record<string, number>;
    unavailable: string[];
    engagement_source?: string | null;
    activity_source?: string | null;
  } | null;
  matched_keywords: string[];
  filter_flags: string[];
};

export type Job = {
  id: number;
  status: "pending" | "running" | "completed" | "failed";
  keywords: string[];
  filters: Record<string, unknown>;
  reference_set_id: number | null;
  progress: Record<string, number | string> | null;
  error: string | null;
  warnings: string[] | null;
  created_at: string;
  completed_at: string | null;
};

export type ReferenceSet = {
  id: number;
  name: string;
  created_at: string;
  embedding_model: string | null;
  images: { id: number; url: string }[];
};

export type AppConfig = {
  weights: Record<
    "visual_similarity" | "activity" | "engagement" | "creator_signal" | "keyword_relevance" | "audience",
    number
  >;
  similarity: { best_weight: number; top_k_weight: number; top_k: number; cosine_floor: number; cosine_ceiling: number };
  activity: Record<string, number>;
  search: {
    default_keywords: string[];
    search_type: "TOP" | "RECENT";
    media_type: "TEXT" | "IMAGE" | "VIDEO" | null;
    page_size: number;
    max_pages_per_keyword: number;
    max_posts_per_keyword: number;
    max_results: number;
    max_images_per_creator: number;
    lookup_profiles: boolean;
    fetch_profile_posts: boolean;
  };
  cache: { profile_ttl_hours: number; posts_ttl_hours: number; embedding_ttl_hours: number };
};

export type ThreadsStatus = {
  app_configured: boolean;
  connected: boolean;
  token_source: "oauth" | "env" | null;
  username: string | null;
  threads_user_id: string | null;
  expires_at: string | null;
  last_refreshed_at: string | null;
  granted_scopes: string[] | null;
  requested_scopes: string[];
  missing_scopes: string[];
  redirect_uri: string;
  keyword_search_budget_remaining: number;
  profile_budget_remaining: number;
};

export type Availability = { metric: string; endpoint?: string; permission?: string; notes: string };

export type SettingsResponse = {
  config: AppConfig;
  threads: ThreadsStatus;
  embedding_model: string;
  data_availability: { available: Availability[]; unavailable: Availability[] };
};

export type TargetProfile = {
  id: number;
  account_id: number;
  username: string;
  selected: boolean;
  note: string | null;
  source: string | null;
  created_at: string;
  profile_url: string;
  creator: Creator | null;
};

export type Account = {
  id: number;
  talent_id: number;
  username: string;
  label: string | null;
  notes: string | null;
  position: number;
  created_at: string;
  profile_url: string;
  profiles_total: number;
  profiles_selected: number;
  profiles?: TargetProfile[];
  talent_name?: string;
};

export type Talent = {
  id: number;
  name: string;
  notes: string | null;
  color: string | null;
  created_at: string;
  accounts: Account[];
};

export type AddProfilesResponse = {
  added: string[];
  duplicates: string[];
  invalid: string[];
  account: Account;
};
