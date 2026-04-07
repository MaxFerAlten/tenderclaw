/** Voice mode types. */

export interface VoiceConfig {
  enabled: boolean;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
}

export type VoiceState = "idle" | "listening" | "processing";

export interface VoiceTranscript {
  final: string;
  interim?: string;
  timestamp: number;
}

export interface VoiceEvent {
  type: "start" | "end" | "transcript" | "error";
  transcript?: VoiceTranscript;
  error?: string;
}