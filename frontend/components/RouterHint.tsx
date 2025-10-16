"use client";

import type { Mode } from "@/types";

interface RouterHintProps {
  selectedMode: Mode;
  inferredMode?: Mode;
  userInput: string;
}

export default function RouterHint({
  selectedMode,
  inferredMode,
  userInput,
}: RouterHintProps) {
  if (!userInput.trim()) {
    return null;
  }

  const displayMode = inferredMode || selectedMode;

  return (
    <div className="router-hint">
      {inferredMode && inferredMode !== selectedMode ? (
        <span>
          Routing to <strong>{displayMode}</strong> mode based on your message
        </span>
      ) : (
        <span>
          Using <strong>{displayMode}</strong> mode
        </span>
      )}
    </div>
  );
}

