/** VoiceButton — microphone button for voice input. */

import { Mic, MicOff } from "lucide-react";

interface VoiceButtonProps {
  isListening: boolean;
  isSupported: boolean;
  onClick: () => void;
  size?: "sm" | "md" | "lg";
}

export function VoiceButton({ isListening, isSupported, onClick, size = "md" }: VoiceButtonProps) {
  if (!isSupported) return null;

  const sizeClasses = {
    sm: "w-8 h-8",
    md: "w-10 h-10",
    lg: "w-12 h-12",
  };

  const iconSizes = {
    sm: "w-4 h-4",
    md: "w-5 h-5",
    lg: "w-6 h-6",
  };

  return (
    <button
      onClick={onClick}
      type="button"
      className={`
        ${sizeClasses[size]}
        rounded-full flex items-center justify-center
        transition-all duration-200
        ${isListening
          ? "bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/50 animate-pulse"
          : "bg-zinc-700 hover:bg-zinc-600 text-zinc-300"
        }
        disabled:opacity-50 disabled:cursor-not-allowed
      `}
      title={isListening ? "Stop listening" : "Start voice input"}
    >
      {isListening ? (
        <Mic className={`${iconSizes[size]} text-white`} />
      ) : (
        <MicOff className={`${iconSizes[size]} text-zinc-400`} />
      )}
    </button>
  );
}