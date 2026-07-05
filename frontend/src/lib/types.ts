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
}

export interface TickerSuggestion {
  symbol: string;
  description: string;
  source: string;
}
