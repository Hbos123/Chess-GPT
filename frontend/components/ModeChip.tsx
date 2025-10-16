"use client";

import type { Mode } from "@/types";

interface ModeChipProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

const MODES: Mode[] = ["PLAY", "ANALYZE", "TACTICS", "DISCUSS"];

export default function ModeChip({ mode, onChange }: ModeChipProps) {
  return (
    <div className="mode-chip">
      <label htmlFor="mode-select">Mode:</label>
      <select
        id="mode-select"
        value={mode}
        onChange={(e) => onChange(e.target.value as Mode)}
        className="mode-select"
      >
        {MODES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  );
}

