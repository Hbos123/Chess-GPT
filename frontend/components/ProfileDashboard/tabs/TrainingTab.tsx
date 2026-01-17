"use client";

import { useState, useEffect } from "react";

interface TrainingTabProps {
  userId: string;
}

export default function TrainingTab({ userId }: TrainingTabProps) {
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<any[]>([]);

  useEffect(() => {
    // In a full implementation, this would fetch from an endpoint
    // that analyzes the profile analytics and generates a training plan.
    // For now, we'll provide some static recommendations based on general logic.
    setRecommendations([
      {
        id: 't1',
        title: 'Endgame Precision',
        description: 'Your endgame accuracy is lower than your opening accuracy. Focus on king and pawn endgames.',
        difficulty: 'Intermediate',
        icon: '👑'
      },
      {
        id: 't2',
        title: 'Tactical Awareness',
        description: 'Several recent games were lost due to tactical blunders in the middlegame.',
        difficulty: 'All levels',
        icon: '⚔️'
      },
      {
        id: 't3',
        title: 'Time Management',
        description: 'You tend to play very fast even in complex positions. Try deliberate thinking drills.',
        difficulty: 'Advanced',
        icon: '⏱️'
      }
    ]);
  }, [userId]);

  return (
    <div className="training-tab">
      <div className="tab-section">
        <h2>Personalized Training Plan</h2>
        <p className="tab-subtitle">Recommendations based on your recent performance and patterns.</p>
        
        <div className="training-grid">
          {recommendations.map((item) => (
            <div key={item.id} className="training-card">
              <div className="training-icon">{item.icon}</div>
              <div className="training-info">
                <h3>{item.title}</h3>
                <p>{item.description}</p>
                <span className="difficulty-tag">{item.difficulty}</span>
              </div>
              <button className="start-training-btn">Start Drill</button>
            </div>
          ))}
        </div>
      </div>

      <div className="tab-section">
        <h2>Suggested Openings</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="stat-label">For White</span>
            <span className="stat-value">London System</span>
            <span className="stat-trend improving">Highest win rate (65%)</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">For Black</span>
            <span className="stat-value">Caro-Kann</span>
            <span className="stat-trend stable">Most consistent (58%)</span>
          </div>
        </div>
      </div>
    </div>
  );
}




