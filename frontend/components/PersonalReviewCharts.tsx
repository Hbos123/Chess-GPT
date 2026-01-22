"use client";

interface PersonalReviewChartsProps {
  data: any;
}

export default function PersonalReviewCharts({ data }: PersonalReviewChartsProps) {
  if (!data) return null;

  // Extract chart data
  const accuracyByRating = data.accuracy_by_rating || [];
  const openingPerformance = data.opening_performance || [];
  const themeFrequency = data.common_mistakes || data.theme_frequency || [];
  const phaseStats = data.phase_stats || { opening: 0, middlegame: 0, endgame: 0 };
  const winRateByPhase = data.win_rate_by_phase || {};
  const accuracyByColor = data.accuracy_by_color || {};
  const performanceByTimeControl = data.performance_by_time_control || [];
  const accuracyByTimeSpent = data.accuracy_by_time_spent || [];
  const performanceByTags = data.performance_by_tags || { top_performing: [], bottom_performing: [] };
  const criticalMoments = data.critical_moments || {};
  const advantageConversion = data.advantage_conversion || {};
  const blunderTriggers = data.blunder_triggers || {};
  const pieceActivity = data.piece_activity || [];

  return (
    <div className="personal-review-charts">
      <h3>📊 Visual Analysis</h3>

      {/* Accuracy Distribution */}
      {accuracyByRating.length > 0 && (
        <div className="chart-section">
          <h4>Accuracy by Rating</h4>
          <div className="bar-chart">
            {accuracyByRating.map((item: any, idx: number) => (
              <div key={idx} className="bar-item">
                <div className="bar-label">{item.rating_range}</div>
                <div className="bar-container">
                  <div
                    className="bar-fill"
                    style={{
                      width: `${item.accuracy}%`,
                      backgroundColor: item.accuracy > 85 ? "#10b981" : item.accuracy > 70 ? "#f59e0b" : "#ef4444"
                    }}
                  >
                    <span className="bar-value">{item.accuracy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="bar-count">{item.game_count} games</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Opening Performance */}
      {openingPerformance.length > 0 && (
        <div className="chart-section">
          <h4>Opening Performance</h4>
          <div className="opening-table">
            <table>
              <thead>
                <tr>
                  <th>Opening</th>
                  <th>Games</th>
                  <th>Win%</th>
                  <th>Avg Accuracy</th>
                  <th>Avg CP Loss</th>
                </tr>
              </thead>
              <tbody>
                {openingPerformance.slice(0, 10).map((opening: any, idx: number) => (
                  <tr key={idx}>
                    <td>{opening.name || "Unknown"}</td>
                    <td>{opening.count}</td>
                    <td style={{ color: opening.win_rate > 50 ? "#10b981" : "#ef4444" }}>
                      {opening.win_rate.toFixed(1)}%
                    </td>
                    <td>{opening.avg_accuracy.toFixed(1)}%</td>
                    <td>{opening.avg_cp_loss.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Theme Frequency */}
      {themeFrequency.length > 0 && (
        <div className="chart-section">
          <h4>Most Common Themes</h4>
          <div className="theme-bars">
            {themeFrequency.slice(0, 10).map((theme: any, idx: number) => (
              <div key={idx} className="theme-item">
                <span className="theme-name">{theme.name}</span>
                <div className="theme-bar-container">
                  <div
                    className="theme-bar"
                    style={{ width: `${(theme.frequency / themeFrequency[0].frequency) * 100}%` }}
                  />
                </div>
                <span className="theme-count">{theme.frequency}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase Statistics */}
      <div className="chart-section">
        <h4>Performance by Phase</h4>
        <div className="phase-stats-grid">
          {Object.entries(phaseStats).map(([phase, stats]: [string, any]) => (
            <div key={phase} className="phase-stat-card">
              <div className="phase-name">
                {phase.charAt(0).toUpperCase() + phase.slice(1)}
              </div>
              <div className="phase-accuracy">
                {stats.move_count === 0 ? "N/A" : `${stats.accuracy?.toFixed(1) || "0.0"}%`}
              </div>
              <div className="phase-detail">
                Avg CP Loss: {stats.move_count === 0 ? "N/A" : (stats.avg_cp_loss?.toFixed(0) || "0")}
              </div>
              <div className="phase-detail">
                {stats.move_count || 0} moves
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Win Rate by Phase */}
      {Object.keys(winRateByPhase).length > 0 && (
        <div className="chart-section">
          <h4>Win Rate by Phase</h4>
          <div className="win-rate-grid">
            {Object.entries(winRateByPhase).map(([phase, rate]: [string, any]) => (
              <div key={phase} className="win-rate-item">
                <div className="win-rate-label">{phase}</div>
                <div className="win-rate-bar-container">
                  <div
                    className="win-rate-bar"
                    style={{
                      width: `${rate}%`,
                      backgroundColor: rate > 50 ? "#10b981" : rate > 40 ? "#f59e0b" : "#ef4444"
                    }}
                  />
                </div>
                <div className="win-rate-value">{rate.toFixed(1)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Performance by Color */}
      {Object.keys(accuracyByColor).length > 0 && (
        <div className="chart-section">
          <h4>Performance by Color</h4>
          <div className="color-comparison">
            {Object.entries(accuracyByColor).map(([color, stats]: [string, any]) => (
              <div key={color} className="color-stat-card">
                <div className="color-icon" style={{ fontSize: '2rem' }}>
                  {color === 'white' ? '⚪' : '⚫'}
                </div>
                <div className="color-name" style={{ textTransform: 'uppercase', fontWeight: 'bold', marginTop: '0.5rem' }}>
                  {color}
                </div>
                <div className="color-accuracy" style={{ fontSize: '1.5rem', fontWeight: 'bold', color: stats.accuracy > 85 ? '#10b981' : stats.accuracy > 70 ? '#f59e0b' : '#ef4444' }}>
                  {stats.accuracy?.toFixed(1) || '0.0'}%
                </div>
                <div className="color-games" style={{ fontSize: '0.9rem', color: '#666' }}>
                  {stats.game_count} games
                </div>
                <div className="color-winrate" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
                  Win Rate: {((stats.win_rate || 0) * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Performance by Time Control */}
      {performanceByTimeControl.length > 0 && (
        <div className="chart-section">
          <h4>Performance by Time Control</h4>
          <div className="time-control-grid">
            {performanceByTimeControl.map((tc: any, idx: number) => (
              <div key={idx} className="time-control-card">
                <div className="tc-name" style={{ textTransform: 'capitalize', fontWeight: 'bold', fontSize: '1.1rem' }}>
                  {tc.time_control}
                </div>
                <div className="tc-accuracy" style={{ fontSize: '1.3rem', fontWeight: 'bold', color: tc.accuracy > 85 ? '#10b981' : tc.accuracy > 70 ? '#f59e0b' : '#ef4444' }}>
                  {tc.accuracy?.toFixed(1) || '0.0'}%
                </div>
                <div className="tc-games" style={{ fontSize: '0.9rem', color: '#666' }}>
                  {tc.game_count} games
                </div>
                <div className="tc-winrate" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
                  {((tc.win_rate || 0) * 100).toFixed(0)}% win rate
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Accuracy by Time Spent */}
      {accuracyByTimeSpent.length > 0 && (
        <div className="chart-section">
          <h4>Accuracy by Time Spent per Move</h4>
          <div className="time-spent-grid">
            {accuracyByTimeSpent.map((range: any, idx: number) => (
              <div key={idx} className="time-spent-card">
                <div className="time-spent-range" style={{ textTransform: 'capitalize', fontWeight: 'bold', fontSize: '1.1rem' }}>
                  {range.time_range}
                </div>
                <div className="time-spent-accuracy" style={{ fontSize: '1.3rem', fontWeight: 'bold', color: range.accuracy > 85 ? '#10b981' : range.accuracy > 70 ? '#f59e0b' : '#ef4444' }}>
                  {range.accuracy?.toFixed(1) || '0.0'}%
                </div>
                <div className="time-spent-moves" style={{ fontSize: '0.9rem', color: '#666' }}>
                  {range.move_count} moves
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Common Mistakes with Weakness Levels */}
      {themeFrequency.length > 0 && (
        <div className="chart-section">
          <h4>Common Themes & Weaknesses</h4>
          <div className="theme-list">
            {themeFrequency.slice(0, 8).map((theme: any, idx: number) => (
              <div key={idx} className="theme-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', borderBottom: '1px solid #eee' }}>
                <div>
                  <span style={{ fontWeight: 'bold' }}>{theme.name}</span>
                  {theme.weakness_level && (
                    <span 
                      style={{ 
                        marginLeft: '0.5rem', 
                        padding: '0.2rem 0.5rem', 
                        borderRadius: '4px', 
                        fontSize: '0.75rem',
                        backgroundColor: theme.weakness_level === 'critical' ? '#fee2e2' : theme.weakness_level === 'moderate' ? '#fef3c7' : '#e5e7eb',
                        color: theme.weakness_level === 'critical' ? '#991b1b' : theme.weakness_level === 'moderate' ? '#92400e' : '#374151'
                      }}
                    >
                      {theme.weakness_level}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.9rem', color: '#666' }}>{theme.frequency} occurrences</span>
                  {theme.error_rate !== undefined && (
                    <span style={{ fontSize: '0.9rem', color: theme.error_rate > 0.4 ? '#dc2626' : theme.error_rate > 0.25 ? '#f59e0b' : '#10b981' }}>
                      {(theme.error_rate * 100).toFixed(0)}% errors
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Performance by Tags */}
      {(performanceByTags.top_performing?.length > 0 || performanceByTags.bottom_performing?.length > 0) && (
        <div className="chart-section">
          <h4>Performance by Position Tags</h4>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Accuracy on moves with specific tactical/strategic tags
          </p>
          
          {/* Top Performing Tags */}
          {performanceByTags.top_performing?.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <h5 style={{ color: '#10b981', fontSize: '1rem', marginBottom: '0.5rem' }}>✅ Strongest Areas</h5>
              <div className="tag-performance-list">
                {performanceByTags.top_performing.map((tag: any, idx: number) => (
                  <div key={idx} className="tag-performance-item" style={{ 
                    borderLeft: '3px solid #10b981'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 'bold', fontSize: '0.95rem' }}>
                          {tag.tag.replace('tag.', '').replace(/\./g, ' › ')}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.2rem' }}>
                          {tag.move_count} moves · {tag.error_count} errors ({tag.error_rate.toFixed(1)}%)
                        </div>
                      </div>
                      <div style={{ 
                        fontSize: '1.2rem', 
                        fontWeight: 'bold', 
                        color: '#10b981' 
                      }}>
                        {tag.accuracy.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bottom Performing Tags */}
          {performanceByTags.bottom_performing?.length > 0 && (
            <div>
              <h5 style={{ color: '#ef4444', fontSize: '1rem', marginBottom: '0.5rem' }}>⚠️ Areas for Improvement</h5>
              <div className="tag-performance-list">
                {performanceByTags.bottom_performing.map((tag: any, idx: number) => (
                  <div key={idx} className="tag-performance-item" style={{ 
                    borderLeft: '3px solid #ef4444'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 'bold', fontSize: '0.95rem' }}>
                          {tag.tag.replace('tag.', '').replace(/\./g, ' › ')}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.2rem' }}>
                          {tag.move_count} moves · {tag.error_count} errors ({tag.error_rate.toFixed(1)}%)
                        </div>
                      </div>
                      <div style={{ 
                        fontSize: '1.2rem', 
                        fontWeight: 'bold', 
                        color: '#ef4444' 
                      }}>
                        {tag.accuracy.toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Critical Moments */}
      {criticalMoments.total_critical > 0 && (
        <div className="chart-section">
          <h4>🔥 Critical Moment Performance</h4>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Performance in high-stakes positions (±200cp evaluation swings)
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#f59e0b' }}>{criticalMoments.total_critical}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Critical Positions</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: criticalMoments.avg_accuracy > 75 ? '#10b981' : '#ef4444' }}>
                {criticalMoments.avg_accuracy?.toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Avg Accuracy</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>{criticalMoments.positions_held}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Held Well</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#ef4444' }}>{criticalMoments.positions_lost}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Mishandled</div>
            </div>
          </div>
        </div>
      )}

      {/* Advantage Conversion */}
      {advantageConversion.winning_positions > 0 && (
        <div className="chart-section">
          <h4>👑 Advantage Conversion Rate</h4>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Ability to convert winning positions (+200cp advantage) into wins
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#3b82f6' }}>{advantageConversion.winning_positions}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Winning Positions</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: advantageConversion.conversion_rate > 75 ? '#10b981' : '#f59e0b' }}>
                {advantageConversion.conversion_rate?.toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Conversion Rate</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>{advantageConversion.conversions}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Converted</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#ef4444' }}>{advantageConversion.squandered}</div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>Squandered</div>
            </div>
          </div>
        </div>
      )}

      {/* Blunder Triggers */}
      {blunderTriggers.total_blunders > 0 && (
        <div className="chart-section">
          <h4>⚠️ What Causes Your Errors</h4>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Understanding when mistakes happen (based on {blunderTriggers.total_blunders} errors)
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#ef4444' }}>
                {blunderTriggers.time_pressure_pct?.toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>⏱️ Time Pressure</div>
              <div style={{ fontSize: '0.8rem', color: '#888' }}>Errors in time trouble</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#f59e0b' }}>
                {blunderTriggers.after_opponent_mistake_pct?.toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>🎯 After Opp Mistake</div>
              <div style={{ fontSize: '0.8rem', color: '#888' }}>Relaxed too soon</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#8b5cf6' }}>
                {blunderTriggers.complex_positions_pct?.toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>🧩 Complex Positions</div>
              <div style={{ fontSize: '0.8rem', color: '#888' }}>6+ active pieces</div>
            </div>
            <div style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#3b82f6' }}>
                {blunderTriggers.simple_positions_pct?.toFixed(0)}%
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>♟️ Simple Positions</div>
              <div style={{ fontSize: '0.8rem', color: '#888' }}>≤3 active pieces</div>
            </div>
          </div>
        </div>
      )}

      {/* Piece Activity */}
      {pieceActivity.length > 0 && (
        <div className="chart-section">
          <h4>♟️ Performance by Piece</h4>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Accuracy when moving each piece type
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem' }}>
            {pieceActivity.map((piece: any, idx: number) => (
              <div key={idx} style={{ 
                padding: '0.75rem', 
                background: 'var(--bg-secondary)', 
                borderRadius: '8px',
                borderLeft: `3px solid ${piece.accuracy > 80 ? '#10b981' : piece.accuracy > 70 ? '#f59e0b' : '#ef4444'}`
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 'bold', fontSize: '1rem' }}>{piece.piece}</div>
                    <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.2rem' }}>
                      {piece.move_count} moves · {piece.error_count} errors
                    </div>
                  </div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 'bold', color: piece.accuracy > 80 ? '#10b981' : piece.accuracy > 70 ? '#f59e0b' : '#ef4444' }}>
                    {piece.accuracy?.toFixed(1)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

