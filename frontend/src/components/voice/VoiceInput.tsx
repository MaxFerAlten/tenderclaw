/** VoiceInput — text input with voice support. */

import { useVoiceMode } from "./useVoiceMode";
import { VoiceButton } from "./VoiceButton";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  placeholder?: string;
}

export function VoiceInput({ onTranscript, placeholder = "Type a message..." }: VoiceInputProps) {
  const {
    isListening,
    isSupported,
    toggleListening,
  } = useVoiceMode({
    onTranscript: (t) => {
      if (t.final) {
        onTranscript(t.final);
      }
    },
  });

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        placeholder={placeholder}
        className="flex-1 px-4 py-3 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-200 focus:outline-none focus:border-blue-500"
      />
      
      <VoiceButton
        isListening={isListening}
        isSupported={isSupported}
        onClick={toggleListening}
        size="md"
      />
      
      {isListening && (
        <div className="flex items-center gap-1 text-xs text-red-400">
          <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          Listening...
        </div>
      )}
    </div>
  );
}