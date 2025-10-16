"use client";

import { useState } from "react";

interface FENDisplayProps {
  fen: string;
  onFenLoad?: (fen: string) => void;
}

export default function FENDisplay({ fen, onFenLoad }: FENDisplayProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedFen, setEditedFen] = useState(fen);
  const [error, setError] = useState("");

  const handleEdit = () => {
    setIsEditing(true);
    setEditedFen(fen);
    setError("");
  };

  const handleSave = () => {
    // Basic FEN validation
    const parts = editedFen.trim().split(/\s+/);
    if (parts.length < 4) {
      setError("Invalid FEN: must have at least 4 parts");
      return;
    }

    // Validate board part
    const rows = parts[0].split('/');
    if (rows.length !== 8) {
      setError("Invalid FEN: board must have 8 ranks");
      return;
    }

    setError("");
    if (onFenLoad) {
      onFenLoad(editedFen.trim());
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedFen(fen);
    setError("");
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(fen);
    // Could add a toast notification here
  };

  if (isEditing) {
    return (
      <div className="fen-display editing">
        <label htmlFor="fen-input">FEN Position:</label>
        <textarea
          id="fen-input"
          value={editedFen}
          onChange={(e) => setEditedFen(e.target.value)}
          className="fen-input"
          rows={3}
        />
        {error && <div className="fen-error">{error}</div>}
        <div className="fen-buttons">
          <button onClick={handleSave} className="fen-save">
            Load
          </button>
          <button onClick={handleCancel} className="fen-cancel">
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fen-display">
      <div className="fen-label">FEN:</div>
      <div className="fen-value" title={fen}>
        {fen}
      </div>
      <div className="fen-actions">
        <button onClick={handleCopy} className="fen-copy" title="Copy FEN">
          📋
        </button>
        <button onClick={handleEdit} className="fen-edit" title="Edit FEN">
          ✏️
        </button>
      </div>
    </div>
  );
}

