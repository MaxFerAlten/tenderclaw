/** Cost tracking types. */

export interface ModelUsage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
  web_search_requests: number;
  cost_usd: number;
  context_window: number;
  max_output_tokens: number;
  api_duration_ms: number;
}

export interface CostSummary {
  session_id: string;
  total_cost_usd: number;
  total_api_duration_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  model_usage: Record<string, ModelUsage>;
}
