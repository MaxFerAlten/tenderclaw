export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
  model: string;
  preview: string;
  total_cost_usd: number;
}

export interface Message {
  role: string;
  content: string | unknown[];
  message_id?: string;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  model: string;
  message_count: number;
  messages: Message[];
  total_usage: {
    input_tokens: number;
    output_tokens: number;
  };
  total_cost_usd: number;
  working_directory: string;
}
