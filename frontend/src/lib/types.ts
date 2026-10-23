export type Role = "central_midfielder" | "winger" | "striker";

export interface StructuredQuery {
  role: Role;
  maximum_age: number | null;
  minimum_minutes: number;
  maximum_market_value_eur: number | null;
  metric_weights: Record<string, number>;
  result_limit: number;
}

export interface MetricInfo {
  key: string;
  label: string;
  short: string;
  group: string;
  description: string;
  unit: string;
}

export interface Profile {
  key: string;
  label: string;
  role: Role;
  weights: Record<string, number>;
  blurb: string;
}

export interface DatasetMeta {
  league: string;
  season: string;
  matches: number;
  players: number;
  stats_source: string;
  valuation_source: string | null;
  valuations_enabled: boolean;
  valuation_window: string;
  age_reference_date: string;
  percentile_pool_min_minutes: number;
  players_matched_to_transfermarkt: number;
  players_unmatched: number;
  built_at: string;
  synthetic: boolean;
}

export interface AppConfig {
  mode: "meta" | "demo";
  model: string | null;
  dataset: DatasetMeta;
  roles: Record<Role, string>;
  metrics: MetricInfo[];
  profiles: Profile[];
  examples: string[];
  limits: { max_text: number; max_results: number; max_compare: number };
}

export interface PlayerMetric {
  key: string;
  label: string;
  short: string;
  group: string;
  unit: string;
  description: string;
  value: number | null;
  percentile: number | null;
  weight: number;
  effective_weight: number;
  contribution: number | null;
}

export interface ValueSignal {
  score_percentile: number;
  value_percentile: number;
  gap: number;
  potentially_undervalued: boolean;
  explanation: string;
}

export interface PlayerResult {
  rank: number;
  id: number;
  name: string;
  display_name: string;
  club: string;
  league: string;
  season: string;
  role: Role;
  role_label: string;
  primary_position: string;
  age: number | null;
  minutes: number;
  matches: number;
  starts: number;
  goals: number | null;
  assists: number | null;
  market_value_eur: number | null;
  valuation_date: string | null;
  valuation_match_confidence: number | null;
  score: number;
  coverage: number;
  metrics: PlayerMetric[];
  strengths: string[];
  tradeoffs: string[];
  missing_data: string[];
  value_signal: ValueSignal | null;
}

export interface SearchResponse {
  mode: "meta" | "demo";
  parse_source: "meta" | "demo" | "demo_fallback" | "manual";
  notes: string[];
  warnings: string[];
  changes?: string[];
  query: StructuredQuery;
  applied_filters: string[];
  profile_label: string | null;
  weights: { key: string; label: string; weight: number }[];
  counts: {
    role_players: number;
    eligible: number;
    excluded: Record<string, number>;
  };
  budget_active: boolean;
  value_analysis: { pool_size: number; valued: number; coverage: number; enabled: boolean };
  percentile_note: string;
  results: PlayerResult[];
}

export interface SummariesResponse {
  source: "meta" | "template" | "template_fallback";
  summaries: Record<string, string>;
  warnings: string[];
  model?: string;
}
