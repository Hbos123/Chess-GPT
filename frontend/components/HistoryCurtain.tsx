import { useState, useEffect, useRef, ReactNode } from 'react';
import type { ProfilePreferences } from './ProfileSetupModal';
import HabitsDashboard from './HabitsDashboard';
import { getBackendBase } from "@/lib/backendBase";
import { supabase } from "@/lib/supabase";

interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

interface ProfileStatusSummary {
  state: string;
  message: string;
  total_accounts: number;
  completed_accounts: number;
  total_games_estimate: number;
  games_indexed: number;
  progress_percent: number;
  last_error?: string | null;
  target_games?: number;
  next_poll_at?: string | null;
  background_active?: boolean;
  light_analyzed_games?: number;
  deep_analyzed_games?: number;
}

interface ProfileHighlight {
  label: string;
  value: string;
  platform?: string;
}

interface ProfileGameSummary {
  game_id?: string;
  opponent_name?: string;
  result?: string;
  platform?: string;
  date?: string;
  url?: string;
  time_category?: string;
  opening?: string;
}

interface ProfileStats {
  overall?: {
    total_games: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
    average_accuracy?: number | null;
    blunder_rate?: number | null;
    mistake_rate?: number | null;
  };
  openings?: {
    top: Array<{ name: string; games: number; win_rate: number; average_accuracy?: number | null; blunder_rate?: number | null }>;
    bottom: Array<{ name: string; games: number; win_rate: number; average_accuracy?: number | null; blunder_rate?: number | null }>;
  };
  tags?: {
    best: Array<{ name: string; games: number; win_rate: number; avg_cp_loss?: number | null }>;
    worst: Array<{ name: string; games: number; win_rate: number; avg_cp_loss?: number | null }>;
  };
  phases?: {
    opening?: number | null;
    middlegame?: number | null;
    endgame?: number | null;
  };
  personality?: {
    notes: string[];
    tendencies: Array<{ title: string; detail: string; confidence?: string }>;
  };
  advanced?: {
    accuracy_by_piece?: Array<{ piece: string; avg_cp_loss: number; error_rate: number; moves: number }>;
    phase_piece_heatmap?: Record<string, Record<string, number>>;
    position_types?: Array<{ type: string; avg_cp_loss: number; error_rate: number; moves: number }>;
    advantage_regimes?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
    tactic_motifs?: Array<{ motif: string; found: number; missed: number; miss_rate: number; avg_loss: number }>;
    tactic_phases?: Array<{ phase: string; opportunities: number; found: number; missed: number }>;
    structural_tags?: Array<{ tag: string; occurrences: number; avg_cp_loss: number; win_rate: number }>;
    weakness?: Record<string, { moves: number; avg_cp_loss: number }>;
    time_buckets?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
    rating_buckets?: Array<{ bucket: string; avg_cp_loss: number; error_rate: number; moves: number }>;
    playstyle?: {
      aggression_bias?: number | null;
      material_bias?: number | null;
      simplification_bias?: number | null;
      king_safety_risk?: number | null;
    };
    conversion?: {
      winning_positions: number;
      converted: number;
      holds: number;
      squandered: number;
      conversion_rate?: number | null;
      max_advantage_cp?: number;
    };
    resilience?: {
      defensive_positions: number;
      swindles: number;
      saves: number;
      collapsed: number;
      save_rate?: number | null;
      max_deficit_cp?: number;
    };
    opening_families?: Array<{ family: string; games: number; win_rate: number }>;
    endgame_skills?: {
      opening_accuracy?: number | null;
      middlegame_accuracy?: number | null;
      endgame_accuracy?: number | null;
    };
  };
  insights?: {
    accuracy?: string[];
    tactics?: string[];
    structure?: string[];
    playstyle?: string[];
    conversion?: string[];
  };
}

interface HistoryCurtainProps {
  open: boolean;
  onClose: () => void;
  onSelectThread: (threadId: string) => void;
  currentThreadId?: string | null;
  onEditProfileSetup?: () => void;
  profilePreferences?: ProfilePreferences | null;
  profileStatus?: ProfileStatusSummary | null;
  profileHighlights?: ProfileHighlight[] | null;
  profileGames?: ProfileGameSummary[] | null;
  profileStats?: ProfileStats | null;
  onRefreshProfile?: () => Promise<void>;
  onOpenProfileDashboard?: () => void;
  onOpenPersonalReview?: () => void;
  userId?: string | null;
  openSettingsNonce?: number;
}

export default function HistoryCurtain({ 
  open, 
  onClose, 
  onSelectThread, 
  currentThreadId,
  onEditProfileSetup,
  profilePreferences,
  profileStatus,
  profileHighlights,
  profileGames,
  profileStats,
  onRefreshProfile,
  onOpenProfileDashboard,
  onOpenPersonalReview,
  userId,
  openSettingsNonce,
}: HistoryCurtainProps) {
  const user = null; // Auth optional for now
  const backendBase = getBackendBase();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [gameSearch, setGameSearch] = useState('');
  const [expandedTab, setExpandedTab] = useState<'personal' | 'settings' | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [maskUsernamesInUI, setMaskUsernamesInUI] = useState(true);
  const [interpreterModel, setInterpreterModel] = useState<string>("");
  const [subscriptionInfo, setSubscriptionInfo] = useState<any>(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionError, setSubscriptionError] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const refreshInProgressRef = useRef(false);
  const lastOpenSettingsNonceRef = useRef<number | null>(null);

  const maskUsername = (u?: string | null) => {
    const s = (u ?? "").trim();
    if (!s) return "Not set";
    if (s.length <= 2) return "*".repeat(s.length);
    const head = s.slice(0, 2);
    const tail = s.length >= 5 ? s.slice(-2) : "";
    const stars = "*".repeat(Math.max(2, s.length - head.length - tail.length));
    return `${head}${stars}${tail}`;
  };

  const formatDate = (iso?: string | null) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return "—";
      return d.toLocaleDateString();
    } catch {
      return "—";
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem("cg_mask_usernames");
      setMaskUsernamesInUI(raw === null ? true : raw === "true");
    } catch {
      setMaskUsernamesInUI(true);
    }
    try {
      setInterpreterModel(window.localStorage.getItem("cg_interpreter_model") ?? "");
    } catch {
      setInterpreterModel("");
    }
  }, []);

  useEffect(() => {
    if (!showSettings) return;
    if (!userId) {
      setSubscriptionInfo(null);
      setSubscriptionError("Sign in to view subscription details.");
      return;
    }

    let cancelled = false;
    (async () => {
      setSubscriptionLoading(true);
      setSubscriptionError("");
      try {
        const url = `${backendBase.replace(/\/$/, "")}/profile/subscription?user_id=${encodeURIComponent(userId)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!cancelled) setSubscriptionInfo(data);
      } catch (e: any) {
        if (!cancelled) setSubscriptionError(e?.message || "Failed to load subscription.");
      } finally {
        if (!cancelled) setSubscriptionLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [showSettings, userId, backendBase]);

  // Watch for openSettingsNonce changes to programmatically open settings
  useEffect(() => {
    if (!open) return;
    if (openSettingsNonce === undefined || openSettingsNonce === null) return;
    if (lastOpenSettingsNonceRef.current === openSettingsNonce) return;
    lastOpenSettingsNonceRef.current = openSettingsNonce;
    setShowSettings(true);
  }, [open, openSettingsNonce]);

  const handleSavePrivacyMask = (next: boolean) => {
    setMaskUsernamesInUI(next);
    try {
      window.localStorage.setItem("cg_mask_usernames", next ? "true" : "false");
    } catch {
      // ignore
    }
  };

  const handleInterpreterModelChange = (next: string) => {
    setInterpreterModel(next);
    try {
      const trimmed = next.trim();
      if (!trimmed) window.localStorage.removeItem("cg_interpreter_model");
      else window.localStorage.setItem("cg_interpreter_model", trimmed);
    } catch {
      // ignore
    }
  };

  const handleManageSubscription = async () => {
    if (!userId) {
      alert("Sign in to manage your subscription.");
      return;
    }
    
    // Get user email from Supabase client
    let userEmail: string | undefined;
    try {
      const { data: { user } } = await supabase.auth.getUser();
      userEmail = user?.email || undefined;
    } catch (e) {
      console.warn("Could not get user email:", e);
    }
    
    try {
      const url = `${backendBase.replace(/\/$/, "")}/billing/portal`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          user_email: userEmail, // Pass email from frontend
          return_url: typeof window !== "undefined" ? window.location.href : undefined,
        }),
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText);
      }
      const data = await res.json();
      if (data?.url) window.open(data.url, "_blank", "noopener,noreferrer");
      else throw new Error("No portal URL returned.");
    } catch (e: any) {
      // Try to parse error message
      let errorMsg = e?.message || "Failed to open billing portal.";
      try {
        const errorJson = JSON.parse(errorMsg);
        errorMsg = errorJson.detail || errorMsg;
      } catch {
        // Not JSON, use as-is
      }
      alert(errorMsg);
    }
  };

  const handleSubscribe = async (productId: string) => {
    if (!userId) {
      alert("Sign in to subscribe.");
      return;
    }
    
    // Get user email
    let userEmail: string | undefined;
    try {
      const { data: { user } } = await supabase.auth.getUser();
      userEmail = user?.email || undefined;
    } catch (e) {
      console.warn("Could not get user email:", e);
    }
    
    try {
      const url = `${backendBase.replace(/\/$/, "")}/stripe/create-checkout`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          user_email: userEmail,
          product_id: productId,
          return_url: typeof window !== "undefined" ? window.location.href : undefined,
        }),
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText);
      }
      const data = await res.json();
      if (data?.url) {
        // Redirect to Stripe Checkout
        window.location.href = data.url;
      } else {
        throw new Error("No checkout URL returned.");
      }
    } catch (e: any) {
      let errorMsg = e?.message || "Failed to create checkout session.";
      try {
        const errorJson = JSON.parse(errorMsg);
        errorMsg = errorJson.detail || errorMsg;
      } catch {
        // Not JSON, use as-is
      }
      alert(errorMsg);
    }
  };

  const linkedAccounts = (profilePreferences?.accounts ?? []).map((account, index) => ({
    id: `${account.platform}-${account.username || index}`,
    platform: account.platform === 'chesscom' ? 'Chess.com' : 'Lichess',
    platformKey: account.platform,
    username: account.username || 'Unknown',
  }));
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>(linkedAccounts.map(acc => acc.id));
  const [gamePage, setGamePage] = useState(0);

  useEffect(() => {
    setSelectedAccounts(linkedAccounts.map(acc => acc.id));
    setGamePage(0);
  }, [profilePreferences]);

  useEffect(() => {
    setGamePage(0);
  }, [gameSearch, selectedAccounts]);

  useEffect(() => {
    if (open && user) {
      loadThreads();
    }
  }, [open]);

  const loadThreads = async () => {
    setLoading(true);
    try {
      // TODO: Load from Supabase
      // const { data } = await supabase
      //   .from('chat_sessions')
      //   .select('*')
      //   .eq('user_id', user.id)
      //   .order('updated_at', { ascending: false });
      // setThreads(data || []);
      setThreads([]);
    } catch (error) {
      console.error('Failed to load threads:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredThreads = threads.filter(t => 
    !search || t.title.toLowerCase().includes(search.toLowerCase())
  );

  const selectedPlatformKeys = new Set(
    linkedAccounts
      .filter(acc => selectedAccounts.includes(acc.id))
      .map(acc => acc.platformKey)
  );

  const filteredGames = (profileGames ?? []).filter(game => {
    const platformKey = (game.platform || '').toLowerCase().includes('lichess') ? 'lichess' : 'chesscom';
    const matchesAccount =
      selectedPlatformKeys.size === 0 ||
      selectedPlatformKeys.has(platformKey) ||
      linkedAccounts.length === 0;
    const opponentName = (game.opponent_name || '').toLowerCase();
    const matchesSearch = !gameSearch || opponentName.includes(gameSearch.toLowerCase());
    return matchesAccount && matchesSearch;
  });
  const gamesPerPage = 5;
  const totalGamePages = Math.max(1, Math.ceil(filteredGames.length / gamesPerPage));
  const pageIndex = Math.min(gamePage, totalGamePages - 1);
  const pagedGames = filteredGames.slice(pageIndex * gamesPerPage, pageIndex * gamesPerPage + gamesPerPage);

  const toggleAccount = (id: string) => {
    setSelectedAccounts(prev => 
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  };

  const renderThreads = () => (
    <div className="thread-list">
      {filteredThreads.map(thread => (
        <button
          key={thread.id}
          className={`thread-item ${currentThreadId === thread.id ? 'active' : ''}`}
          onClick={() => {
            onSelectThread(thread.id);
            onClose();
          }}
        >
          <div className="thread-title">{thread.title}</div>
          <div className="thread-meta">
            {new Date(thread.updated_at).toLocaleDateString()}
            {thread.message_count && ` • ${thread.message_count} messages`}
          </div>
        </button>
      ))}
    </div>
  );

  const formatAccounts = () => {
    if (!profilePreferences?.accounts?.length) {
      return "Link Chess.com or Lichess usernames to personalise analysis.";
    }
    const accounts = profilePreferences.accounts;
    const counts = accounts.reduce<Record<string, number>>((acc, item) => {
      const platformRaw = String((item as any).platform || "");
      const platformLabel =
        platformRaw === "chesscom" || platformRaw === "chess.com"
          ? "Chess.com"
          : "Lichess";
      acc[platformLabel] = (acc[platformLabel] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts)
      .map(([label, n]) => `${label}: ${n} linked`)
      .join(" · ");
  };

  const formatControls = () => {
    if (!profilePreferences?.timeControls?.length) {
      return "Select bullet, blitz or rapid to index.";
    }
    return profilePreferences.timeControls
      .map((tc) => tc.charAt(0).toUpperCase() + tc.slice(1))
      .join(", ");
  };

  const highlightCards = (profileHighlights && profileHighlights.length > 0)
    ? profileHighlights
    : [
        { label: 'Games indexed', value: '—', platform: 'All' },
        { label: 'Win rate (last 10)', value: '—', platform: 'All' },
      ];

  const overallStats = profileStats?.overall;
  const openingTop = profileStats?.openings?.top ?? [];
  const openingBottom = profileStats?.openings?.bottom ?? [];
  const tagBest = profileStats?.tags?.best ?? [];
  const tagWorst = profileStats?.tags?.worst ?? [];

  const renderStatsSummary = () => {
    if (!overallStats) return null;
    return (
      <section className="personal-section">
        <header>
          <h3>Performance snapshot</h3>
        </header>
        <div className="stats-summary-grid">
          <div className="stat-card">
            <p className="stat-label">Total games indexed</p>
            <p className="stat-value">{overallStats.total_games}</p>
            <span className="stat-platform">sample size</span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Win rate</p>
            <p className="stat-value">{overallStats.win_rate}%</p>
            <span className="stat-platform">
              {overallStats.wins}-{overallStats.losses}-{overallStats.draws}
            </span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Average accuracy</p>
            <p className="stat-value">
              {overallStats.average_accuracy ?? "—"}%
            </p>
            <span className="stat-platform">per Chess.com reports</span>
          </div>
          <div className="stat-card">
            <p className="stat-label">Errors per game</p>
            <p className="stat-value">
              {overallStats.blunder_rate ?? "—"}/{overallStats.mistake_rate ?? "—"}
            </p>
            <span className="stat-platform">blunders / mistakes</span>
          </div>
        </div>
      </section>
    );
  };

  const renderOpeningPerformance = () => {
    if (!openingTop.length && !openingBottom.length) return null;
    return (
      <section className="personal-section">
        <header>
          <h3>Opening performance</h3>
        </header>
        <div className="opening-grid">
          {openingTop.length > 0 && (
            <div>
              <h4>Best lines</h4>
              <table className="opening-table">
                <thead>
                  <tr>
                    <th>Opening</th>
                    <th>Win %</th>
                    <th>Acc%</th>
                  </tr>
                </thead>
                <tbody>
                  {openingTop.map(op => (
                    <tr key={`opening-top-${op.name}`}>
                      <td>{op.name}</td>
                      <td>{op.win_rate}%</td>
                      <td>{op.average_accuracy ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {openingBottom.length > 0 && (
            <div>
              <h4>Needs attention</h4>
              <table className="opening-table">
                <thead>
                  <tr>
                    <th>Opening</th>
                    <th>Win %</th>
                    <th>Acc%</th>
                  </tr>
                </thead>
                <tbody>
                  {openingBottom.map(op => (
                    <tr key={`opening-bottom-${op.name}`}>
                      <td>{op.name}</td>
                      <td>{op.win_rate}%</td>
                      <td>{op.average_accuracy ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    );
  };

  const renderTagInsights = () => {
    if (!tagBest.length && !tagWorst.length) return null;
    return (
      <section className="personal-section">
        <header>
          <h3>Tag insights</h3>
        </header>
        <div className="tag-grid">
          {tagBest.length > 0 && (
            <div className="tag-panel">
              <h4>Top strengths</h4>
              {tagBest.map(tag => (
                <div key={`tag-best-${tag.name}`} className="tag-row">
                  <span>{tag.name}</span>
                  <span>{tag.win_rate}% WR</span>
                </div>
              ))}
            </div>
          )}
          {tagWorst.length > 0 && (
            <div className="tag-panel">
              <h4>Stretch goals</h4>
              {tagWorst.map(tag => (
                <div key={`tag-worst-${tag.name}`} className="tag-row">
                  <span>{tag.name}</span>
                  <span>{tag.win_rate}% WR</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    );
  };

  const renderAccuracyBreakdown = () => {
    if (!profileStats?.phases) return null;
    const { opening, middlegame, endgame } = profileStats.phases;
    if (![opening, middlegame, endgame].some((v) => v !== undefined && v !== null)) {
      return null;
    }
    return (
      <section className="personal-section">
        <header>
          <h3>Accuracy by phase</h3>
        </header>
        <div className="phase-grid">
          <div className="phase-card">
            <p className="stat-label">Opening</p>
            <p className="stat-value">{opening ?? "—"}%</p>
          </div>
          <div className="phase-card">
            <p className="stat-label">Middlegame</p>
            <p className="stat-value">{middlegame ?? "—"}%</p>
          </div>
          <div className="phase-card">
            <p className="stat-label">Endgame</p>
            <p className="stat-value">{endgame ?? "—"}%</p>
          </div>
        </div>
      </section>
    );
  };

  const renderPersonality = () => {
    if (!profileStats?.personality) return null;
    const { notes = [], tendencies = [] } = profileStats.personality;
    if (!notes.length && !tendencies.length) return null;
    return (
      <section className="personal-section">
        <header>
          <h3>Personality & tendencies</h3>
        </header>
        <div className="personality-grid">
          <div className="personality-card">
            <h4>Highlights</h4>
            <ul>
              {notes.map((note, idx) => (
                <li key={`personality-note-${idx}`}>{note}</li>
              ))}
            </ul>
          </div>
          <div className="personality-card">
            <h4>Tendencies</h4>
            {tendencies.length === 0 ? (
              <p className="text-secondary">Need more data to map preferences.</p>
            ) : (
              tendencies.map((trend, idx) => (
                <div key={`personality-trend-${idx}`} className="tendency-row">
                  <h5>{trend.title}</h5>
                  <p>{trend.detail}</p>
                  {trend.confidence && <span className="trend-confidence">{trend.confidence}</span>}
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    );
  };

  const renderAdvancedInsights = () => {
    const advanced = profileStats?.advanced;
    if (!advanced) return null;
    const {
      accuracy_by_piece: pieceRows = [],
      phase_piece_heatmap: heatmap = {},
      position_types: positionRows = [],
      advantage_regimes: advantageRows = [],
      tactic_motifs: tacticRows = [],
      tactic_phases: tacticPhaseRows = [],
      structural_tags: structuralRows = [],
      weakness: weaknessSummary = {},
      time_buckets: timeRows = [],
      rating_buckets: ratingRows = [],
      playstyle,
      conversion,
      resilience,
      opening_families: familyRows = [],
      endgame_skills: endgameSkills,
    } = advanced;
    const heatmapPieces = Array.from(
      new Set(
        Object.values(heatmap || {}).flatMap((row) => Object.keys(row || {}))
      )
    );

    const renderPlaystyleBar = (
      label: string,
      value?: number | null,
      leftLabel = "Positional",
      rightLabel = "Attacking"
    ) => {
      if (value === undefined || value === null) return null;
      return (
        <div className="playstyle-row">
          <div className="playstyle-label">{label}</div>
          <div className="playstyle-track">
            <span>{leftLabel}</span>
            <div className="playstyle-meter">
              <span className="playstyle-fill" style={{ width: `${value}%` }} />
            </div>
            <span>{rightLabel}</span>
          </div>
        </div>
      );
    };

    return (
      <>
        {pieceRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Accuracy by piece</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Piece</th>
                  <th>Avg CP loss</th>
                  <th>Error rate</th>
                  <th>Samples</th>
                </tr>
              </thead>
              <tbody>
                {pieceRows.map((row) => (
                  <tr key={`piece-row-${row.piece}`}>
                    <td>{row.piece}</td>
                    <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                    <td>{row.error_rate.toFixed(1)}%</td>
                    <td>{row.moves}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {!!heatmapPieces.length && (
          <section className="personal-section">
            <header>
              <h3>Phase × piece heatmap</h3>
            </header>
            <div className="heatmap-wrapper">
              <table className="advanced-table heatmap">
                <thead>
                  <tr>
                    <th>Phase</th>
                    {heatmapPieces.map((piece) => (
                      <th key={`heathead-${piece}`}>{piece}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(heatmap).map(([phase, row]) => (
                    <tr key={`heat-${phase}`}>
                      <td>{phase}</td>
                      {heatmapPieces.map((piece) => (
                        <td key={`${phase}-${piece}`}>
                          {row?.[piece] !== undefined
                            ? `${row[piece].toFixed(1)} cp`
                            : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {positionRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Position type performance</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Avg CP loss</th>
                  <th>Error rate</th>
                  <th>Samples</th>
                </tr>
              </thead>
              <tbody>
                {positionRows.map((row) => (
                  <tr key={`pos-${row.type}`}>
                    <td>{row.type}</td>
                    <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                    <td>{row.error_rate.toFixed(1)}%</td>
                    <td>{row.moves}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {advantageRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Advantage regimes</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Regime</th>
                  <th>Avg CP loss</th>
                  <th>Error rate</th>
                  <th>Moves</th>
                </tr>
              </thead>
              <tbody>
                {advantageRows.map((row) => (
                  <tr key={`adv-${row.bucket}`}>
                    <td>{row.bucket.replace("_", " ")}</td>
                    <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                    <td>{row.error_rate.toFixed(1)}%</td>
                    <td>{row.moves}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {tacticRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Tactical motifs</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Motif</th>
                  <th>Found</th>
                  <th>Missed</th>
                  <th>Miss rate</th>
                  <th>Avg miss loss</th>
                </tr>
              </thead>
              <tbody>
                {tacticRows.map((row) => (
                  <tr key={`tactic-${row.motif}`}>
                    <td>{row.motif}</td>
                    <td>{row.found}</td>
                    <td>{row.missed}</td>
                    <td>{row.miss_rate.toFixed(1)}%</td>
                    <td>{row.avg_loss.toFixed(1)} cp</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {tacticPhaseRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Tactics by phase</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Phase</th>
                  <th>Opportunities</th>
                  <th>Found</th>
                  <th>Missed</th>
                </tr>
              </thead>
              <tbody>
                {tacticPhaseRows.map((row) => (
                  <tr key={`tactic-phase-${row.phase}`}>
                    <td>{row.phase}</td>
                    <td>{row.opportunities}</td>
                    <td>{row.found}</td>
                    <td>{row.missed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {structuralRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Structural tags</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Tag</th>
                  <th>Avg CP loss</th>
                  <th>Win rate</th>
                  <th>Samples</th>
                </tr>
              </thead>
              <tbody>
                {structuralRows.map((row) => (
                  <tr key={`struct-${row.tag}`}>
                    <td>{row.tag}</td>
                    <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                    <td>{row.win_rate.toFixed(1)}%</td>
                    <td>{row.occurrences}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {(timeRows.length > 0 || ratingRows.length > 0) && (
          <section className="personal-section">
            <header>
              <h3>Time & rating pressure</h3>
            </header>
            <div className="dual-table">
              {timeRows.length > 0 && (
                <table className="advanced-table compact">
                  <thead>
                    <tr>
                      <th>Time bucket</th>
                      <th>Avg CP loss</th>
                      <th>Error rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeRows.map((row) => (
                      <tr key={`time-${row.bucket}`}>
                        <td>{row.bucket}</td>
                        <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                        <td>{row.error_rate.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {ratingRows.length > 0 && (
                <table className="advanced-table compact">
                  <thead>
                    <tr>
                      <th>Opponent</th>
                      <th>Avg CP loss</th>
                      <th>Error rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ratingRows.map((row) => (
                      <tr key={`rating-${row.bucket}`}>
                        <td>{row.bucket.replace("_", " ")}</td>
                        <td>{row.avg_cp_loss.toFixed(1)} cp</td>
                        <td>{row.error_rate.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        )}

        {(playstyle?.aggression_bias !== undefined ||
          playstyle?.material_bias !== undefined ||
          playstyle?.simplification_bias !== undefined) && (
          <section className="personal-section">
            <header>
              <h3>Playstyle sliders</h3>
            </header>
            <div className="playstyle-grid">
              {renderPlaystyleBar("Aggression bias", playstyle?.aggression_bias, "Positional", "Attacking")}
              {renderPlaystyleBar("Material vs initiative", playstyle?.material_bias, "Initiative", "Material")}
              {renderPlaystyleBar("Simplification", playstyle?.simplification_bias, "Keep tension", "Simplify")}
              {playstyle?.king_safety_risk !== undefined && playstyle.king_safety_risk !== null && (
                <p className="summary-line">
                  King safety errors on {playstyle.king_safety_risk.toFixed(1)}% of king-focused moves.
                </p>
              )}
            </div>
          </section>
        )}

        {(conversion || resilience) && (
          <section className="personal-section">
            <header>
              <h3>Conversion & resilience</h3>
            </header>
            <div className="conversion-grid">
              {conversion && (
                <div className="stat-card">
                  <p className="stat-label">Winning positions</p>
                  <p className="stat-value">
                    {conversion.converted}/{conversion.winning_positions || 0}
                  </p>
                  <span className="stat-platform">
                    {conversion.conversion_rate ? `${conversion.conversion_rate}% converted` : 'Need samples'}
                  </span>
                </div>
              )}
              {resilience && (
                <div className="stat-card">
                  <p className="stat-label">Defensive saves</p>
                  <p className="stat-value">
                    {resilience.swindles + resilience.saves}/{resilience.defensive_positions || 0}
                  </p>
                  <span className="stat-platform">
                    {resilience.save_rate ? `${resilience.save_rate}% held` : 'Need samples'}
                  </span>
                </div>
              )}
            </div>
          </section>
        )}

        {familyRows.length > 0 && (
          <section className="personal-section">
            <header>
              <h3>Opening families</h3>
            </header>
            <table className="advanced-table">
              <thead>
                <tr>
                  <th>Family</th>
                  <th>Games</th>
                  <th>Win %</th>
                </tr>
              </thead>
              <tbody>
                {familyRows.slice(0, 6).map((row) => (
                  <tr key={`family-${row.family}`}>
                    <td>{row.family}</td>
                    <td>{row.games}</td>
                    <td>{row.win_rate.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {endgameSkills && (
          <section className="personal-section">
            <header>
              <h3>Phase accuracy snapshot</h3>
            </header>
            <div className="phase-grid">
              <div className="phase-card">
                <p className="stat-label">Opening</p>
                <p className="stat-value">
                  {endgameSkills.opening_accuracy ?? "—"}%
                </p>
              </div>
              <div className="phase-card">
                <p className="stat-label">Middlegame</p>
                <p className="stat-value">
                  {endgameSkills.middlegame_accuracy ?? "—"}%
                </p>
              </div>
              <div className="phase-card">
                <p className="stat-label">Endgame</p>
                <p className="stat-value">
                  {endgameSkills.endgame_accuracy ?? "—"}%
                </p>
              </div>
            </div>
          </section>
        )}

        {(weaknessSummary?.opponent?.moves || weaknessSummary?.self?.moves) && (
          <section className="personal-section">
            <header>
              <h3>Weakness exploitation</h3>
            </header>
            <div className="conversion-grid">
              {weaknessSummary.opponent && (
                <div className="stat-card">
                  <p className="stat-label">When opponent is weak</p>
                  <p className="stat-value">
                    {weaknessSummary.opponent.avg_cp_loss?.toFixed(1)} cp
                  </p>
                  <span className="stat-platform">
                    {weaknessSummary.opponent.moves} samples
                  </span>
                </div>
              )}
              {weaknessSummary.self && (
                <div className="stat-card">
                  <p className="stat-label">When you are weak</p>
                  <p className="stat-value">
                    {weaknessSummary.self.avg_cp_loss?.toFixed(1)} cp
                  </p>
                  <span className="stat-platform">
                    {weaknessSummary.self.moves} samples
                  </span>
                </div>
              )}
            </div>
          </section>
        )}
      </>
    );
  };

  const renderInsightNarrative = () => {
    const insights = profileStats?.insights;
    if (!insights) return null;
    const entries = Object.entries(insights).filter(
      ([, lines]) => Array.isArray(lines) && lines.length > 0
    );
    if (!entries.length) return null;
    const labelMap: Record<string, string> = {
      accuracy: "Accuracy",
      tactics: "Tactics",
      structure: "Structure",
      playstyle: "Playstyle",
      conversion: "Conversion",
    };
    return (
      <section className="personal-section">
        <header>
          <h3>Insight highlights</h3>
        </header>
        <div className="insight-columns">
          {entries.map(([key, lines]) => (
            <div key={`insight-${key}`} className="insight-column">
              <h4>{labelMap[key] || key}</h4>
              <ul>
                {(lines as string[]).map((line, idx) => (
                  <li key={`${key}-line-${idx}`}>{line}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    );
  };

  const renderProgress = () => {
    if (!profileStatus) {
      return (
        <p className="analysis-placeholder">
          Comprehensive style insights and improvement plan will appear here once your accounts
          finish syncing. Expect opening distribution, time-management breakdowns, and targeted drills.
        </p>
      );
    }

    const target = profileStatus.target_games || Math.max(1, profileStatus.total_games_estimate || profileStatus.games_indexed || 1);
    const fetched = profileStatus.games_indexed;
    const analyzed = Math.min(profileStatus.deep_analyzed_games || 0, fetched);
    const fetchPercent = target ? Math.min(100, (fetched / target) * 100) : 0;
    const analyzedPercent = fetched ? fetchPercent * (analyzed / fetched) : 0;

    return (
      <div className="profile-progress">
        <div className="profile-progress-head">
          <span>{profileStatus.message}</span>
          <span>{Math.round(fetchPercent)}%</span>
        </div>
        <div className="profile-progress-bar">
          <div className="progress-segment segment-fetched" style={{ width: `${fetchPercent}%` }} />
          <div className="progress-segment segment-deep" style={{ width: `${analyzedPercent}%` }} />
        </div>
        <p className="summary-line">
          {fetched} fetched • {analyzed} analyzed
          {profileStatus.last_error ? ` • ${profileStatus.last_error}` : null}
        </p>
        <div className="profile-progress-legend">
          <span><span className="legend-dot fetched" /> Fetched</span>
          <span><span className="legend-dot deep" /> Analyzed</span>
        </div>
        {profileStatus.background_active && (
          <p className="profile-progress-hint">Quietly indexing in the background…</p>
        )}
        {profileStatus.next_poll_at && (
          <p className="profile-progress-hint">
            Next refresh around {new Date(profileStatus.next_poll_at).toLocaleTimeString()}
          </p>
        )}
      </div>
    );
  };

  const renderPersonalDetail = (): ReactNode => (
    <>
      <section className="personal-section">
        <header className="personal-row">
          <h3>Profile setup</h3>
          {onEditProfileSetup && (
            <button type="button" className="ghost small" onClick={onEditProfileSetup}>
              Edit setup
            </button>
          )}
        </header>
        {profilePreferences ? (
          <>
            <p className="summary-line">{formatAccounts()}</p>
            <p className="summary-line">Time controls: {formatControls()}</p>
          </>
        ) : (
          <p className="summary-line" style={{ color: '#9ca3af', fontStyle: 'italic' }}>
            Loading profile data... (Check console for details)
          </p>
        )}
      </section>
      <section className="personal-section">
        <header>
          <h3>Linked accounts</h3>
        </header>
        <div className="account-filter-row">
          {linkedAccounts.map(account => (
            <button
              key={account.id}
              className={`account-chip ${selectedAccounts.includes(account.id) ? 'active' : ''}`}
              onClick={() => toggleAccount(account.id)}
            >
              {account.platform} · {account.username}
            </button>
          ))}
        </div>
      </section>

      <section className="personal-section">
        <header>
          <h3>Highlights</h3>
        </header>
        <div className="stats-grid">
          {highlightCards.map(stat => (
            <div key={`${stat.label}-${stat.platform}`} className="stat-card">
              <p className="stat-label">{stat.label}</p>
              <p className="stat-value">{stat.value}</p>
              {stat.platform && (
                <span className="stat-platform">{stat.platform}</span>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="personal-section">
        <header className="personal-row">
          <h3>Previous games</h3>
          <input
            type="text"
            value={gameSearch}
            onChange={(e) => setGameSearch(e.target.value)}
            placeholder="Search opponent..."
            className="search-input compact"
          />
        </header>
        {filteredGames.length === 0 ? (
          <div className="empty-state">No games match your filters.</div>
        ) : (
          <div className="game-list">
            {pagedGames.map(game => (
              <div key={game.game_id || `${game.platform}-${game.date}-${game.opponent_name}`} className="game-card">
                <div>
                <p className="game-opponent">{game.opponent_name || 'Unknown opponent'}</p>
                  <p className="game-meta">
                    {game.date ? new Date(game.date).toLocaleDateString() : '—'} • {(game.result || '').toUpperCase()}
                  </p>
                  <p className="game-opening">
                    {game.opening ? game.opening : 'Opening unknown'}
                  </p>
                </div>
                <span className="game-platform">
                {(game.platform || '').toLowerCase().includes('lichess') ? 'Lichess' : 'Chess.com'}
                </span>
              </div>
            ))}
            {totalGamePages > 1 && (
              <div className="game-pagination">
                <button
                  type="button"
                  onClick={() => setGamePage(prev => Math.max(0, prev - 1))}
                  disabled={pageIndex === 0}
                >
                  Previous
                </button>
                <span>
                  Page {pageIndex + 1} / {totalGamePages}
                </span>
                <button
                  type="button"
                  onClick={() => setGamePage(prev => Math.min(totalGamePages - 1, prev + 1))}
                  disabled={pageIndex >= totalGamePages - 1}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="personal-section">
        <header>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <h3 style={{ margin: 0 }}>Profile analysis</h3>
            {onOpenPersonalReview && (
              <button
                type="button"
                className="ghost small"
                onClick={() => {
                  onOpenPersonalReview();
                  onClose();
                }}
              >
                Personal Review
              </button>
            )}
          </div>
        </header>
        {renderProgress()}
      </section>
      
      {/* New Habits Dashboard - replaces tag insights with richer visualization */}
      {userId && (
        <section className="personal-section habits-section">
          <HabitsDashboard userId={userId} onRefresh={onRefreshProfile} />
        </section>
      )}
      
      {renderStatsSummary()}
      {renderOpeningPerformance()}
      {renderAccuracyBreakdown()}
      {renderPersonality()}
      {renderAdvancedInsights()}
      {renderInsightNarrative()}

    </>
  );

  const renderSettingsDetail = (): ReactNode => (
    <div className="curtain-content">
      <form className="settings-form" onSubmit={(e) => e.preventDefault()}>
        <fieldset className="settings-group">
          <legend>Privacy</legend>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={maskUsernamesInUI}
              onChange={(e) => handleSavePrivacyMask(e.target.checked)}
            />
            <span>Mask usernames in UI (recommended)</span>
          </label>
          <p className="settings-note">
            Helps keep screenshots share-safe by masking your linked usernames throughout the app.
          </p>
        </fieldset>

        <fieldset className="settings-group">
          <legend>AI</legend>
          <label>
            Interpreter model override
            <input
              type="text"
              value={interpreterModel}
              onChange={(e) => handleInterpreterModelChange(e.target.value)}
              placeholder='e.g. gpt-5-nano (leave blank for default)'
            />
          </label>
          <p className="settings-note">
            Leave blank to use the backend default. This setting affects how requests are interpreted before tools run.
          </p>
        </fieldset>

        <fieldset className="settings-group">
          <legend>Chess accounts</legend>
          <p className="settings-note">
            To link your chess accounts, use the “Personal” area and click “Edit profile setup”.
          </p>
          {profilePreferences?.accounts && profilePreferences.accounts.length > 0 ? (
            <div className="linked-accounts-list">
              {profilePreferences.accounts.map((acc, idx) => {
                const platformRaw = String((acc as any).platform || "");
                const platformLabel =
                  platformRaw === "chesscom" || platformRaw === "chess.com"
                    ? "Chess.com"
                    : "Lichess";
                const usernameLabel = maskUsernamesInUI ? maskUsername(acc.username) : (acc.username || "Not set");
                return (
                  <div key={idx} className="linked-account-item">
                    <span className="account-platform">{platformLabel}</span>
                    <span className="account-username">{usernameLabel}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="settings-empty">No accounts linked yet.</p>
          )}
        </fieldset>

        <fieldset className="settings-group">
          <legend>Subscription</legend>

          {!userId && <p className="settings-empty">Sign in to view your subscription.</p>}
          {userId && subscriptionLoading && <p className="settings-empty">Loading subscription…</p>}
          {userId && !subscriptionLoading && subscriptionError && (
            <p className="settings-empty">{subscriptionError}</p>
          )}

          {userId && !subscriptionLoading && !subscriptionError && subscriptionInfo && (
            <div style={{ marginBottom: 24 }}>
              <div className="linked-accounts-list" style={{ marginBottom: 16 }}>
                <div className="linked-account-item">
                  <span className="account-platform">Current Plan</span>
                  <span className="account-username">
                    {subscriptionInfo?.tier?.name ?? subscriptionInfo?.tier_id ?? "Unpaid"}
                  </span>
                </div>
                <div className="linked-account-item">
                  <span className="account-platform">Status</span>
                  <span className="account-username">{subscriptionInfo?.status ?? "unknown"}</span>
                </div>
                <div className="linked-account-item">
                  <span className="account-platform">Renews</span>
                  <span className="account-username">{formatDate(subscriptionInfo?.current_period_end)}</span>
                </div>
              </div>

              <div className="account-button-row">
                <button type="button" onClick={handleManageSubscription}>
                  Manage subscription
                </button>
              </div>

              <p className="settings-note" style={{ marginTop: 12 }}>
                Billing, invoices, and cancellations are handled in the Stripe customer portal.
              </p>
            </div>
          )}

          {/* Subscription Tiers */}
          <div className="stripe-pricing-table-container">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ padding: '20px', border: '1px solid var(--border-color)', borderRadius: '8px', background: 'var(--bg-secondary)' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600' }}>Lite</h3>
                <p style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)', fontSize: '14px' }}>Perfect for casual players</p>
                <button
                  type="button"
                  onClick={() => handleSubscribe('prod_TqH4CqNKemJjTi')}
                  disabled={!userId}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: userId ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                    color: userId ? 'var(--bg-primary)' : 'var(--text-secondary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: userId ? 'pointer' : 'not-allowed',
                    fontSize: '14px',
                    fontWeight: '600',
                    transition: 'background 0.2s',
                    opacity: userId ? 1 : 0.6,
                  }}
                  onMouseEnter={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-primary)';
                    }
                  }}
                >
                  {userId ? 'Subscribe to Lite' : 'Sign in to Subscribe'}
                </button>
              </div>
              
              <div style={{ padding: '20px', border: '1px solid var(--border-color)', borderRadius: '8px', background: 'var(--bg-secondary)' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600' }}>Starter</h3>
                <p style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)', fontSize: '14px' }}>For serious players</p>
                <button
                  type="button"
                  onClick={() => handleSubscribe('prod_TqH4m9kERqeESC')}
                  disabled={!userId}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: userId ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                    color: userId ? 'var(--bg-primary)' : 'var(--text-secondary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: userId ? 'pointer' : 'not-allowed',
                    fontSize: '14px',
                    fontWeight: '600',
                    transition: 'background 0.2s',
                    opacity: userId ? 1 : 0.6,
                  }}
                  onMouseEnter={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-primary)';
                    }
                  }}
                >
                  {userId ? 'Subscribe to Starter' : 'Sign in to Subscribe'}
                </button>
              </div>
              
              <div style={{ padding: '20px', border: '1px solid var(--border-color)', borderRadius: '8px', background: 'var(--bg-secondary)' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '600' }}>Full</h3>
                <p style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)', fontSize: '14px' }}>Unlimited access</p>
                <button
                  type="button"
                  onClick={() => handleSubscribe('prod_TqH5itxYTmQls0')}
                  disabled={!userId}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: userId ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                    color: userId ? 'var(--bg-primary)' : 'var(--text-secondary)',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: userId ? 'pointer' : 'not-allowed',
                    fontSize: '14px',
                    fontWeight: '600',
                    transition: 'background 0.2s',
                    opacity: userId ? 1 : 0.6,
                  }}
                  onMouseEnter={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (userId) {
                      e.currentTarget.style.background = 'var(--accent-primary)';
                    }
                  }}
                >
                  {userId ? 'Subscribe to Full' : 'Sign in to Subscribe'}
                </button>
              </div>
            </div>
          </div>
        </fieldset>
      </form>
    </div>
  );

  if (!open) return null;

  return (
    <>
      <div className="curtain-overlay" onClick={onClose} />
      <div className="history-curtain">
        <div className="curtain-header">
          <h2>Chesster Hub</h2>
          <button onClick={onClose} className="close-button">Close</button>
        </div>

        <div className="curtain-summary vertical">
          <button className="summary-card summary-button" onClick={async () => {
            if (onOpenProfileDashboard) {
              onOpenProfileDashboard();
              onClose();
              return;
            }
            // Fallback to old behavior if prop not provided
            setExpandedTab('personal');
            
            // Then refresh in background (if not already refreshing)
            if (onRefreshProfile && !refreshInProgressRef.current) {
              refreshInProgressRef.current = true;
              setIsRefreshing(true);
              
              // Refresh in background - don't block UI
              onRefreshProfile()
                .then(() => {
                  console.log("✅ Profile refresh completed");
                })
                .catch((err) => {
                  console.error("❌ Refresh failed:", err);
                })
                .finally(() => {
                  setIsRefreshing(false);
                  refreshInProgressRef.current = false;
                });
            }
          }}>
            <div className="summary-card-head">
              <h3>Personal {isRefreshing && '⟳'}</h3>
            </div>
            <div className="summary-card-body">
              {isRefreshing ? (
                <p className="summary-line">Loading profile data...</p>
              ) : (
                <>
                  <p className="summary-line">{formatAccounts()}</p>
                  <p className="summary-line">Time controls: {formatControls()}</p>
                </>
              )}
            </div>
          </button>

          <button className="summary-card summary-button" onClick={() => setShowSettings(true)}>
            <div className="summary-card-head">
              <h3>Settings</h3>
            </div>
            <div className="summary-card-body">
              <p className="summary-line">Default mode: Discuss</p>
              <p className="summary-line">Engine: Adaptive</p>
            </div>
          </button>
        </div>
      </div>

      {expandedTab && (
        <div className="curtain-detail-overlay">
          <div className="curtain-detail-panel slide-in">
            <header>
              <button onClick={() => setExpandedTab(null)}>← Back</button>
              <h2>{expandedTab === 'personal' ? 'Personal dashboard' : 'Settings'}</h2>
              <div />
            </header>
            <div className="curtain-detail-body">
              {expandedTab === 'personal' ? renderPersonalDetail() : renderSettingsDetail()}
            </div>
          </div>
        </div>
      )}


      {showSettings && (
        <div
          className="settings-fullscreen-overlay"
          onClick={() => setShowSettings(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
        >
          <div className="settings-fullscreen-modal" onClick={(e) => e.stopPropagation()}>
            <div className="settings-fullscreen-header">
              <h2>Settings</h2>
              <button className="close-button" onClick={() => setShowSettings(false)}>
                ×
              </button>
            </div>
            <div className="settings-fullscreen-body">{renderSettingsDetail()}</div>
          </div>
        </div>
      )}

    </>
  );
}

