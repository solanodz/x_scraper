export interface Engagement {
  reply_count: number;
  retweet_count: number;
  like_count: number;
  quote_count: number;
  bookmarked_count: number;
}

export interface ClusterSource {
  id_str: string;
  source_type: string;
  username: string;
}

export interface SignalSummary {
  id_str: string;
  published_at: string;
  username: string;
  raw_content: string;
  source: string;
  cashtags: string[];
  url: string;
  engagement: Engagement;
  source_type?: string;
  title?: string | null;
  summary?: string | null;
  body?: string | null;
  canonical_url?: string | null;
  relevance_score?: number | null;
  topic?: string | null;
  sentiment?: string | null;
  cluster_id?: string | null;
  cluster_sources?: ClusterSource[];
}

export interface SignalDetail extends SignalSummary {
  hashtags: string[];
  article: Record<string, unknown> | null;
  payload: Record<string, unknown>;
}

export interface ChatCitation {
  id_str: string;
  username: string;
  url: string;
  excerpt: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  /** Pasos del agente (solo durante streaming; no persistidos). */
  steps?: ResearchStep[];
}

export interface ResearchStep {
  tool: string;
  label: string;
  status: "running" | "done";
}

export interface ChatSessionSummary {
  id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageRecord {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[] | null;
  created_at: string;
}

export interface Quote {
  symbol: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  timestamp: string | null;
  delayed?: boolean;
  available?: boolean;
  logo?: string | null;
}

export interface TickerLogoEntry {
  symbol: string;
  logo: string | null;
}

export interface TickerSuggestion {
  symbol: string;
  description: string;
  source: string;
}

export interface TickerWatchEntry {
  id: string;
  symbol: string;
  note?: string | null;
  created_at: string;
}

export interface DossierBlockContent {
  blocks: Record<string, string>;
  sentiment_stats?: Record<string, number | string | Record<string, number>>;
}

export interface DossierVersion {
  id: string;
  symbol: string;
  content: DossierBlockContent;
  citations: ChatCitation[];
  created_at: string;
}

export interface ChartPlanAssessmentDimension {
  summary?: string;
  stance?: "alcista" | "bajista" | "neutral" | string | null;
  findings?: string[];
}

export interface ChartPlanAssessment {
  summary?: string;
  visual?: ChartPlanAssessmentDimension | null;
  narrative?: ChartPlanAssessmentDimension | null;
  sentiment_vs_price?: ChartPlanAssessmentDimension | null;
  multi_tf?: ChartPlanAssessmentDimension | null;
  conflicts: string[];
  data_gaps: string[];
  bias_check: string;
  bullish_count?: number | null;
  bearish_count?: number | null;
}

export interface ChartPlanView {
  type: "tradingview" | "sentiment_bars" | "signals_timeline" | string;
  enabled: boolean;
  interval?: string | null;
  rationale?: string | null;
}

export interface ChartPlanChartData {
  sentiment_bars?: Array<{ label: string; count: number }>;
  signals_timeline?: Array<{ date: string; count: number }>;
}

export interface ChartPlanPineScript {
  title: string;
  code: string;
  purpose: string;
  limitations: string;
}

export interface ChartPlanTimeframe {
  interval?: string;
  rationale?: string;
}

export interface ChartPlanTradingViewStudy {
  id: string;
  inputs?: Record<string, number | string>;
}

export interface ChartPlanIndicatorReading {
  name: string;
  stance: "alcista" | "bajista" | "neutral" | string;
  reading: string;
  tv_study?: ChartPlanTradingViewStudy | null;
}

/** Soft view for Operator-first Ticker Chart (ADR-0011). */
export interface ChartPlanSuggestedView {
  interval: string;
  period: string;
  sma_a: { enabled: boolean; length: number };
  sma_b: { enabled: boolean; length: number };
  donchian: { enabled: boolean; period: number };
  fib: boolean;
  volume: boolean;
}

export interface ChartPlanContent {
  symbol?: string;
  timeframes?: Array<ChartPlanTimeframe | string>;
  views: ChartPlanView[];
  chart_data?: ChartPlanChartData;
  suggested_view?: ChartPlanSuggestedView;
  /** Pine off for MVP; may be empty or omitted. */
  pine_scripts?: ChartPlanPineScript[];
  indicator_readings?: ChartPlanIndicatorReading[];
  tradingview_studies?: ChartPlanTradingViewStudy[];
  assessment: ChartPlanAssessment;
  summary?: string | null;
}

export interface ChartPlanVersion {
  id: string;
  symbol: string;
  content: ChartPlanContent;
  dossier_version_id?: string | null;
  created_at: string;
}

export interface PriceCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  /** Unix seconds (opcional; intradía puede usar date ISO datetime). */
  time?: number;
}

export interface PriceCandlesResponse {
  symbol: string;
  period: string;
  interval?: string;
  candles: PriceCandle[];
  data_points: number;
  error?: string | null;
}
