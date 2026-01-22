import React from 'react';

interface GameReviewTableProps {
  data: {
    moves?: Array<{
      moveNumber?: number;
      move?: string;
      quality?: string;
      cpLoss?: number;
      eval?: number;
      comment?: string;
    }>;
    stats?: {
      accuracy?: number;
      mistakes?: number;
      blunders?: number;
      missed_wins?: number;
      white_accuracy?: number;
      black_accuracy?: number;
      excellent?: number;
      good?: number;
      inaccuracy?: number;
      mistake?: number;
      blunder?: number;
    };
    game_metadata?: {
      opening?: string;
      total_moves?: number;
      game_character?: string;
      result?: string;
    };
    key_points?: Array<{
      ply?: number;
      type?: string;
      description?: string;
      move?: string;
    }>;
  };
}

export default function GameReviewTable({ data }: GameReviewTableProps) {
  const { moves = [], stats = {}, game_metadata = {}, key_points = [] } = data;

  const getQualityClass = (quality: string | undefined) => {
    if (!quality) return '';
    const q = quality.toLowerCase();
    if (q.includes('excellent') || q.includes('best')) return 'quality-excellent';
    if (q.includes('good')) return 'quality-good';
    if (q.includes('inaccuracy')) return 'quality-inaccuracy';
    if (q.includes('mistake') && !q.includes('blunder')) return 'quality-mistake';
    if (q.includes('blunder')) return 'quality-blunder';
    return '';
  };

  return (
    <div className="game-review-table-container">
      {/* Game Metadata Header */}
      {game_metadata.opening && (
        <div className="review-metadata">
          <div className="metadata-row">
            <span className="metadata-label">Opening:</span>
            <span className="metadata-value">{game_metadata.opening}</span>
          </div>
          {game_metadata.total_moves && (
            <div className="metadata-row">
              <span className="metadata-label">Total Moves:</span>
              <span className="metadata-value">{game_metadata.total_moves}</span>
            </div>
          )}
          {game_metadata.game_character && (
            <div className="metadata-row">
              <span className="metadata-label">Game Character:</span>
              <span className="metadata-value">{game_metadata.game_character}</span>
            </div>
          )}
          {game_metadata.result && (
            <div className="metadata-row">
              <span className="metadata-label">Result:</span>
              <span className="metadata-value">{game_metadata.result}</span>
            </div>
          )}
        </div>
      )}

      {/* Accuracy Stats */}
      {stats && Object.keys(stats).length > 0 && (
        <div className="review-stats">
          <div className="stats-title">Statistics</div>
          <div className="stats-grid">
            {stats.white_accuracy !== undefined && (
              <div className="stat-item">
                <span className="stat-label">White Accuracy:</span>
                <span className="stat-value">{stats.white_accuracy}%</span>
              </div>
            )}
            {stats.black_accuracy !== undefined && (
              <div className="stat-item">
                <span className="stat-label">Black Accuracy:</span>
                <span className="stat-value">{stats.black_accuracy}%</span>
              </div>
            )}
            {stats.accuracy !== undefined && (
              <div className="stat-item">
                <span className="stat-label">Overall Accuracy:</span>
                <span className="stat-value">{stats.accuracy}%</span>
              </div>
            )}
            {stats.excellent !== undefined && stats.excellent > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-excellent">Excellent:</span>
                <span className="stat-value">{stats.excellent}</span>
              </div>
            )}
            {stats.good !== undefined && stats.good > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-good">Good:</span>
                <span className="stat-value">{stats.good}</span>
              </div>
            )}
            {stats.inaccuracy !== undefined && stats.inaccuracy > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-inaccuracy">Inaccuracies:</span>
                <span className="stat-value">{stats.inaccuracy}</span>
              </div>
            )}
            {stats.mistake !== undefined && stats.mistake > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-mistake">Mistakes:</span>
                <span className="stat-value">{stats.mistake}</span>
              </div>
            )}
            {stats.blunder !== undefined && stats.blunder > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-blunder">Blunders:</span>
                <span className="stat-value">{stats.blunder}</span>
              </div>
            )}
            {stats.missed_wins !== undefined && stats.missed_wins > 0 && (
              <div className="stat-item">
                <span className="stat-label quality-blunder">Missed Wins:</span>
                <span className="stat-value">{stats.missed_wins}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Key Moments */}
      {key_points && key_points.length > 0 && (
        <div className="review-key-moments">
          <div className="key-moments-title">Key Moments</div>
          <div className="key-moments-list">
            {key_points.slice(0, 10).map((point, idx) => (
              <div key={idx} className="key-moment-item">
                <span className="moment-type">{point.type || 'Critical'}</span>
                {point.move && <span className="moment-move">{point.move}</span>}
                {point.ply && <span className="moment-ply">Move {Math.ceil(point.ply / 2)}</span>}
                <span className="moment-desc">{point.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Move Table (only show if moves exist and are annotated) */}
      {moves && moves.length > 0 && moves.some(m => m.quality) && (
        <div className="review-moves">
          <div className="moves-title">Move-by-Move Analysis</div>
          <table className="game-review-table">
            <thead>
              <tr>
                <th>Move #</th>
                <th>Move</th>
                <th>Quality</th>
                <th>CP Loss</th>
                <th>Eval</th>
                <th>Comment</th>
              </tr>
            </thead>
            <tbody>
              {moves.filter(m => m.quality).slice(0, 50).map((move, idx) => (
                <tr key={idx}>
                  <td>{move.moveNumber || Math.ceil((idx + 1) / 2)}</td>
                  <td className="move-san">{move.move || '-'}</td>
                  <td className={getQualityClass(move.quality)}>
                    {move.quality || '-'}
                  </td>
                  <td className="cp-loss">
                    {move.cpLoss !== undefined ? `${move.cpLoss}cp` : '-'}
                  </td>
                  <td className="eval">
                    {move.eval !== undefined ? `${move.eval > 0 ? '+' : ''}${(move.eval / 100).toFixed(2)}` : '-'}
                  </td>
                  <td className="move-comment">{move.comment || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}




