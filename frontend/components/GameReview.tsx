"use client";

import { useState } from "react";
import { getBackendBase } from "@/lib/backendBase";

interface GameReviewProps {
  pgn: string;
  onReviewComplete?: (report: any) => void;
}

export default function GameReview({ pgn, onReviewComplete }: GameReviewProps) {
  const [isReviewing, setIsReviewing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [report, setReport] = useState<any>(null);
  const BACKEND_BASE = getBackendBase();

  const handleReview = async () => {
    if (!pgn || pgn.trim().length === 0) {
      alert("No game to review! Play some moves first.");
      return;
    }

    setIsReviewing(true);
    setProgress(0);

    try {
      // Call backend to review game
      // This is a simplified version - full implementation would show progress
      const response = await fetch(`${BACKEND_BASE}/review_game?pgn_string=${encodeURIComponent(pgn)}`, {
        method: 'POST'
      });

      if (!response.ok) {
        throw new Error('Review failed');
      }

      const reviewData = await response.json();
      setReport(reviewData);
      setProgress(100);

      if (onReviewComplete) {
        onReviewComplete(reviewData);
      }
    } catch (err) {
      console.error('Review error:', err);
      alert('Review failed. Make sure backend is running.');
    } finally {
      setIsReviewing(false);
    }
  };

  return (
    <div className="game-review-container">
      <button 
        onClick={handleReview}
        disabled={isReviewing || !pgn}
        className="review-button"
      >
        {isReviewing ? `Reviewing... ${progress}%` : '📊 Review Game'}
      </button>

      {report && (
        <div className="review-report">
          <h3>Game Review Report</h3>
          <div className="review-summary">
            <div>Total Moves: {report.moves?.length || 0}</div>
            <div>Critical Moves: {report.moves?.filter((m: any) => m.isCritical).length || 0}</div>
            <div>Missed Wins: {report.moves?.filter((m: any) => m.isMissedWin).length || 0}</div>
          </div>
        </div>
      )}
    </div>
  );
}

