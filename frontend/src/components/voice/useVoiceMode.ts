/** useVoiceMode — React hook for voice input. */

import { useState, useEffect, useCallback, useRef } from "react";
import type { VoiceConfig, VoiceState, VoiceTranscript } from "./types";

interface UseVoiceModeOptions {
  config?: Partial<VoiceConfig>;
  onTranscript?: (transcript: VoiceTranscript) => void;
  onError?: (error: string) => void;
}

interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  [index: number]: { transcript: string };
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

export function useVoiceMode(options: UseVoiceModeOptions = {}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcripts, setTranscripts] = useState<VoiceTranscript[]>([]);
  const [isSupported, setIsSupported] = useState(false);
  
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  
  const configRef = useRef<VoiceConfig>({
    enabled: true,
    continuous: true,
    interimResults: true,
    lang: "en-US",
    ...options.config,
  });

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = configRef.current.continuous;
      recognition.interimResults = configRef.current.interimResults;
      recognition.lang = configRef.current.lang;
      
      recognition.onstart = () => setState("listening");
      recognition.onend = () => setState("idle");
      recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
        setState("idle");
        optionsRef.current.onError?.(e.error);
      };
      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const result = event.results[event.results.length - 1];
        const transcript: VoiceTranscript = {
          final: result.isFinal ? result[0].transcript : "",
          interim: !result.isFinal ? result[0].transcript : undefined,
          timestamp: Date.now(),
        };
        
        setTranscripts(prev => [...prev, transcript]);
        optionsRef.current.onTranscript?.(transcript);
      };
      
      recognitionRef.current = recognition;
    }
    
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  const startListening = useCallback(() => {
    if (recognitionRef.current && state === "idle") {
      try {
        recognitionRef.current.start();
        setState("listening");
      } catch {
        // Already started
      }
    }
  }, [state]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current && state === "listening") {
      recognitionRef.current.stop();
      setState("idle");
    }
  }, [state]);

  const toggleListening = useCallback(() => {
    if (state === "listening") {
      stopListening();
    } else {
      startListening();
    }
  }, [state, startListening, stopListening]);

  const clearTranscripts = useCallback(() => {
    setTranscripts([]);
  }, []);

  const getFinalTranscript = useCallback(() => {
    return transcripts
      .filter(t => t.final)
      .map(t => t.final)
      .join(" ");
  }, [transcripts]);

  return {
    state,
    transcripts,
    isSupported,
    isListening: state === "listening",
    startListening,
    stopListening,
    toggleListening,
    clearTranscripts,
    getFinalTranscript,
  };
}