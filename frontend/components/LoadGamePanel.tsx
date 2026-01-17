import { useEffect, useMemo, useState } from 'react';
import type { DragEvent, ChangeEvent } from 'react';
import { Chess } from 'chess.js';
import Board from '@/components/Board';
import { analyzeBoardPhoto, lookupGames as fetchLookupGames, type LookupGameSummary, type VisionBoardResponse } from '@/lib/api';

export type LoadedGamePayload = {
  fen: string;
  pgn?: string;
  orientation?: 'white' | 'black';
  source?: 'pgn' | 'fen' | 'link' | 'lookup' | 'photo';
  whitePlayer?: string;
  blackPlayer?: string;
};

interface LoadGamePanelProps {
  onLoad: (payload: LoadedGamePayload) => void;
  onClose: () => void;
}

type LookupGame = LookupGameSummary;

export default function LoadGamePanel({ onLoad, onClose }: LoadGamePanelProps) {
  const [activeTab, setActiveTab] = useState<'pgn' | 'fen' | 'link' | 'lookup' | 'photo'>('pgn');
  const [pgnInput, setPgnInput] = useState('');
  const [fenInput, setFenInput] = useState('');
  const [linkInput, setLinkInput] = useState('');
  const [lookupUser, setLookupUser] = useState('');
  const [lookupOpponent, setLookupOpponent] = useState('');
  const [lookupGames, setLookupGames] = useState<LookupGame[] | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupPlatformUsed, setLookupPlatformUsed] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<string>('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [photoPreset, setPhotoPreset] = useState<'digital' | 'physical'>('digital');
  const [photoOrientationHint, setPhotoOrientationHint] = useState<'white' | 'black'>('white');
  const [visionResult, setVisionResult] = useState<VisionBoardResponse | null>(null);
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionError, setVisionError] = useState<string | null>(null);
  const [fenOverride, setFenOverride] = useState('');

  useEffect(() => {
    if (!photoFile) {
      setPhotoPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(photoFile);
    setPhotoPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  const resetVisionState = () => {
    setVisionResult(null);
    setFenOverride('');
    setVisionError(null);
  };

  const handlePhotoSelection = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setVisionError('Please upload a valid image file.');
      return;
    }
    setPhotoFile(file);
    resetVisionState();
  };

  const handlePhotoInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    handlePhotoSelection(file);
  };

  const handleDropPhoto = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    handlePhotoSelection(file || null);
  };

  const handleAnalyzePhoto = async () => {
    if (!photoFile) {
      setVisionError('Attach a board photo first.');
      return;
    }
    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('preset', photoPreset);
    formData.append('orientation_hint', photoOrientationHint);
    setVisionLoading(true);
    setVisionError(null);
    try {
      const result = await analyzeBoardPhoto(formData);
      setVisionResult(result);
      setFenOverride(result.fen);
      setPhotoOrientationHint(result.orientation);
    } catch (err: any) {
      setVisionError(err?.message || 'Unable to analyze this photo.');
      setVisionResult(null);
    } finally {
      setVisionLoading(false);
    }
  };

  const handleUseVisionFen = () => {
    if (!visionResult) return;
    const fenToUse = fenOverride.trim() || visionResult.fen;
    onLoad({
      fen: fenToUse,
      source: 'photo',
      orientation: photoOrientationHint,
    });
    onClose();
  };

  const filteredLookupGames = useMemo(() => {
    if (!lookupGames) return [];
    const normalizedUser = lookupUser.trim().toLowerCase();
    if (!lookupOpponent.trim()) return lookupGames;
    const filter = lookupOpponent.trim().toLowerCase();
    return lookupGames.filter((game) => {
      const white = game.white.toLowerCase();
      const black = game.black.toLowerCase();
      let opponentName = '';
      if (normalizedUser && white === normalizedUser && black !== normalizedUser) {
        opponentName = game.black;
      } else if (normalizedUser && black === normalizedUser && white !== normalizedUser) {
        opponentName = game.white;
      } else {
        opponentName = `${game.white} ${game.black}`;
      }
      return opponentName.toLowerCase().includes(filter);
    });
  }, [lookupGames, lookupOpponent, lookupUser]);

  const handleLookupSearch = async () => {
    if (!lookupUser.trim()) {
      setError('Enter a username to look up recent games');
      return;
    }
    setError('');
    setLookupError(null);
    console.log('[LoadGamePanel] 🔎 Lookup search triggered', {
      username: lookupUser.trim(),
      opponentFilter: lookupOpponent.trim(),
    });
    setLookupLoading(true);
    try {
      const platforms = ['chess.com', 'lichess', 'combined'];
      let games: LookupGame[] = [];
      let used: string | null = null;
      for (const platform of platforms) {
        const batch = await fetchLookupGames(
          lookupUser.trim(),
          lookupOpponent.trim() || undefined,
          platform
        );
        console.log('[LoadGamePanel] 📥 Backend returned games', {
          platform,
          count: batch.length,
        });
        if (batch.length > 0) {
          games = batch;
          used = platform;
          break;
        }
      }
      setLookupPlatformUsed(used);
      setLookupGames(games);
      if (!used || games.length === 0) {
        setLookupError('No games found for this search. Try another opponent or broaden the filter.');
      }
    } catch (err: any) {
      console.error('[LoadGamePanel] ❌ Lookup failed', err);
      setLookupGames(null);
      setLookupPlatformUsed(null);
      setLookupError(err?.message || 'Failed to fetch games. Please try again.');
    } finally {
      setLookupLoading(false);
    }
  };

  const handleSelectLookupGame = (game: LookupGame) => {
    const normalizedUser = lookupUser.trim().toLowerCase();
    let orientation: 'white' | 'black' | undefined;
    if (normalizedUser) {
      if (game.white.toLowerCase() === normalizedUser) {
        orientation = 'white';
      } else if (game.black.toLowerCase() === normalizedUser) {
        orientation = 'black';
      }
    }
    console.log('[LoadGamePanel] 🎯 Game selected from lookup', {
      id: game.id,
      white: game.white,
      black: game.black,
      orientation,
      fenPreview: game.fen,
      pgnLength: game.pgn?.length || 0,
    });
    onLoad({
      fen: game.fen,
      pgn: game.pgn,
      orientation,
      source: 'lookup',
      whitePlayer: game.white,
      blackPlayer: game.black,
    });
    onClose();
  };

  const canLoad = useMemo(() => {
    if (activeTab === 'pgn') return Boolean(pgnInput.trim());
    if (activeTab === 'fen') return Boolean(fenInput.trim());
    if (activeTab === 'link') return false;
    if (activeTab === 'lookup') return false;
    return false;
  }, [activeTab, pgnInput, fenInput]);

  const validatePGN = (pgn: string) => {
    try {
      const game = new Chess();
      (game as any).loadPgn(pgn, { sloppy: true });
      setPreview(`Valid game: ${game.history().length} moves`);
      setError('');
      return true;
    } catch (e: any) {
      setError('Invalid PGN format');
      setPreview('');
      return false;
    }
  };

  const validateFEN = (fen: string) => {
    try {
      const game = new Chess(fen);
      setPreview(`Valid position: ${game.turn() === 'w' ? 'White' : 'Black'} to move`);
      setError('');
      return true;
    } catch (e: any) {
      setError('Invalid FEN format');
      setPreview('');
      return false;
    }
  };

  const handleLoad = () => {
    if (!canLoad) return;
    if (activeTab === 'pgn' && pgnInput.trim()) {
      if (validatePGN(pgnInput)) {
        const game = new Chess();
        (game as any).loadPgn(pgnInput, { sloppy: true });
        console.log('[LoadGamePanel] ✅ PGN validated', {
          moveCount: game.history().length,
          pgnLength: pgnInput.length,
        });
        onLoad({
          fen: game.fen(),
          pgn: pgnInput,
          source: 'pgn',
        });
        onClose();
      }
    } else if (activeTab === 'fen' && fenInput.trim()) {
      if (validateFEN(fenInput)) {
        console.log('[LoadGamePanel] ✅ FEN validated and ready to send');
        onLoad({
          fen: fenInput,
          source: 'fen',
        });
        onClose();
      }
    } else if (activeTab === 'link' && linkInput.trim()) {
      // TODO: Fetch game from Chess.com/Lichess API
      setError('Link import not yet implemented');
    }
  };

  return (
    <div className="load-game-modal-overlay" onClick={onClose}>
      <div className="load-game-modal" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h3>Load Game</h3>
          <button onClick={onClose} className="panel-close">×</button>
        </div>

      <div className="panel-tabs">
        <button 
          className={activeTab === 'pgn' ? 'active' : ''}
          onClick={() => setActiveTab('pgn')}
        >
          PGN
        </button>
        <button 
          className={activeTab === 'fen' ? 'active' : ''}
          onClick={() => setActiveTab('fen')}
        >
          FEN
        </button>
        <button 
          className={activeTab === 'link' ? 'active' : ''}
          onClick={() => setActiveTab('link')}
        >
          Link
        </button>
        <button 
          className={activeTab === 'lookup' ? 'active' : ''}
          onClick={() => setActiveTab('lookup')}
        >
          Lookup
        </button>
        <button
          className={activeTab === 'photo' ? 'active' : ''}
          onClick={() => setActiveTab('photo')}
        >
          Photo
        </button>
      </div>

      <div className="panel-content">
        {activeTab === 'pgn' && (
          <textarea
            value={pgnInput}
            onChange={(e) => {
              setPgnInput(e.target.value);
              if (e.target.value.trim()) validatePGN(e.target.value);
            }}
            placeholder="Paste PGN here..."
            rows={8}
            className="panel-input"
          />
        )}

        {activeTab === 'fen' && (
          <input
            type="text"
            value={fenInput}
            onChange={(e) => {
              setFenInput(e.target.value);
              if (e.target.value.trim()) validateFEN(e.target.value);
            }}
            placeholder="Paste FEN here..."
            className="panel-input"
          />
        )}

        {activeTab === 'link' && (
          <input
            type="text"
            value={linkInput}
            onChange={(e) => setLinkInput(e.target.value)}
            placeholder="Chess.com or Lichess game URL..."
            className="panel-input"
          />
        )}

        {activeTab === 'lookup' && (
          <div className="lookup-section">
            <div className="lookup-input-row">
              <div className="lookup-field">
                <label>Player username</label>
                <input
                  type="text"
                  value={lookupUser}
                  onChange={(e) => setLookupUser(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleLookupSearch();
                  }}
                  placeholder="Search Chess.com / Lichess handle..."
                />
              </div>
              <button
                type="button"
                className="lookup-search-button"
                onClick={handleLookupSearch}
                disabled={lookupLoading}
              >
                {lookupLoading ? 'Searching...' : 'Search'}
              </button>
            </div>

            {(lookupLoading || lookupGames || lookupError) && (
              <div className="lookup-table-wrapper">
                {lookupPlatformUsed && (
                  <div className="lookup-platform-note">
                    Showing recent {lookupPlatformUsed} games
                  </div>
                )}
                <div className="lookup-field">
                  <label>vs opponent</label>
                  <input
                    type="text"
                    value={lookupOpponent}
                    onChange={(e) => setLookupOpponent(e.target.value)}
                    placeholder="Filter by opponent..."
                  />
                </div>

                {lookupLoading && (
                  <div className="lookup-empty">Searching recent classical & rapid games...</div>
                )}

                {!lookupLoading && lookupError && (
                  <div className="lookup-empty">{lookupError}</div>
                )}

                {!lookupLoading && lookupGames && filteredLookupGames.length === 0 && (
                  <div className="lookup-empty">No games matched this opponent filter.</div>
                )}

                {!lookupLoading && filteredLookupGames.length > 0 && (
                  <div className="lookup-table-scroll">
                    <table className="lookup-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>White</th>
                          <th>Black</th>
                          <th>Result</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredLookupGames.map((game) => (
                          <tr key={game.id} onClick={() => handleSelectLookupGame(game)}>
                            <td>{game.date}</td>
                            <td>{game.white}</td>
                            <td>{game.black}</td>
                            <td>{game.result}</td>
                            <td>
                              <button
                                type="button"
                                className="lookup-use-button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSelectLookupGame(game);
                                }}
                              >
                                Use
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {!lookupLoading && !lookupGames && !lookupError && (
              <div className="lookup-empty muted">Search a player to see recent games.</div>
            )}
          </div>
        )}

        {activeTab === 'photo' && (
          <div className="photo-section">
            <div
              className={`photo-dropzone ${photoFile ? 'has-file' : ''}`}
              onDrop={handleDropPhoto}
              onDragOver={(event) => event.preventDefault()}
            >
              {photoPreviewUrl ? (
                <img src={photoPreviewUrl} alt="Uploaded board preview" />
              ) : (
                <p>
                  Drag & drop a board photo here or use the buttons below.
                  <br />
                  Digital mode works best with Chess GPT screenshots. Physical boards are experimental.
                </p>
              )}
            </div>

            <div className="photo-input-row">
              <label className="photo-button">
                Upload image
                <input type="file" accept="image/*" onChange={handlePhotoInputChange} />
              </label>
              <label className="photo-button">
                Use camera
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={handlePhotoInputChange}
                />
              </label>
            </div>

            <button
              className="photo-analyze-button"
              onClick={handleAnalyzePhoto}
              disabled={visionLoading || !photoFile}
            >
              {visionLoading ? 'Analyzing photo...' : 'Send to analyzer'}
            </button>

            {visionError && <div className="panel-error">{visionError}</div>}

            {visionResult && (
              <div className="photo-result">
                <div className="photo-board-preview">
                  <Board
                    fen={fenOverride || visionResult.fen}
                    onMove={() => {}}
                    orientation={photoOrientationHint}
                    disabled
                  />
                </div>
                <textarea
                  value={fenOverride}
                  onChange={(e) => setFenOverride(e.target.value)}
                  rows={3}
                  className="panel-input"
                  placeholder="Detected FEN"
                />
                <div className="photo-confidence">
                  Model confidence: {Math.round(visionResult.confidence * 100)}% · Orientation:{' '}
                  {photoOrientationHint === 'white' ? 'White bottom' : 'Black bottom'}
                </div>
                {visionResult.uncertain_squares?.length > 0 && (
                  <div className="photo-uncertain">
                    <div className="photo-uncertain-title">Squares to double-check:</div>
                    <div className="photo-uncertain-list">
                      {visionResult.uncertain_squares.map((sq) => (
                        <span key={`${sq.square}-${sq.piece}`} className="photo-badge">
                          {sq.square.toUpperCase()} {sq.piece ?? ''} ({Math.round(sq.confidence * 100)}%)
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {visionResult.notes && <div className="photo-notes">{visionResult.notes}</div>}
                <button
                  className="photo-use-button"
                  onClick={handleUseVisionFen}
                  disabled={!fenOverride.trim()}
                >
                  Use this position
                </button>
              </div>
            )}

            <div className="photo-privacy-note">
              Images are temporarily processed and sent to OpenAI (gpt-4o-mini) to recognise the board.
            </div>
          </div>
        )}

        {error && <div className="panel-error">{error}</div>}
        {preview && <div className="panel-preview">{preview}</div>}
      </div>

      <div className="panel-footer">
        <button onClick={handleLoad} className="load-button" disabled={!canLoad}>
          Use in chat
        </button>
      </div>
      </div>
    </div>
  );
}

