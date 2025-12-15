"use client";

interface PersonalReviewReportProps {
  report: string;
  data: any;
  query: string;
}

export default function PersonalReviewReport({ report, data, query }: PersonalReviewReportProps) {
  // Parse report sections if structured
  const sections = report.split(/\n## /);
  const overview = sections[0];
  const otherSections = sections.slice(1);

  return (
    <div className="personal-review-report">
      <div className="query-display">
        <strong>Your Question:</strong> {query}
      </div>

      <div className="report-overview">
        {overview.split('\n').map((line, idx) => (
          <p key={idx}>{line}</p>
        ))}
      </div>

      {otherSections.length > 0 && (
        <div className="report-sections">
          {otherSections.map((section, idx) => {
            const lines = section.split('\n');
            const title = lines[0];
            const content = lines.slice(1).join('\n');

            return (
              <div key={idx} className="report-section">
                <h4>{title}</h4>
                <div className="report-content">
                  {content.split('\n').map((line, lineIdx) => {
                    // Format bullet points
                    if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
                      return (
                        <li key={lineIdx} className="report-bullet">
                          {line.trim().substring(1).trim()}
                        </li>
                      );
                    }
                    // Format bold text
                    const formattedLine = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    return (
                      <p key={lineIdx} dangerouslySetInnerHTML={{ __html: formattedLine }} />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Key Statistics Summary */}
      {data.summary && (
        <div className="statistics-summary">
          <h4>📈 Key Statistics</h4>
          <div className="stats-grid">
            {data.summary.total_games && (
              <div className="stat-item">
                <div className="stat-label">Total Games</div>
                <div className="stat-value">{data.summary.total_games}</div>
              </div>
            )}
            {data.summary.overall_accuracy && (
              <div className="stat-item">
                <div className="stat-label">Overall Accuracy</div>
                <div className="stat-value">{data.summary.overall_accuracy.toFixed(1)}%</div>
              </div>
            )}
            {data.summary.win_rate !== undefined && (
              <div className="stat-item">
                <div className="stat-label">Win Rate</div>
                <div className="stat-value">{data.summary.win_rate.toFixed(1)}%</div>
              </div>
            )}
            {data.summary.avg_cp_loss && (
              <div className="stat-item">
                <div className="stat-label">Avg CP Loss</div>
                <div className="stat-value">{data.summary.avg_cp_loss.toFixed(0)}</div>
              </div>
            )}
            {data.summary.blunder_rate && (
              <div className="stat-item">
                <div className="stat-label">Blunder Rate</div>
                <div className="stat-value">{data.summary.blunder_rate.toFixed(1)}%</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Action Plan */}
      {data.action_plan && data.action_plan.length > 0 && (
        <div className="action-plan">
          <h4>🎯 Recommended Actions</h4>
          <ol className="action-list">
            {data.action_plan.map((action: string, idx: number) => (
              <li key={idx}>{action}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

