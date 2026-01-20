"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import TopBar from "@/components/TopBar";
import HistoryCurtain from "@/components/HistoryCurtain";
import BottomComposer from "@/components/BottomComposer";
import BoardDock from "@/components/BoardDock";
import TabBar, { BoardTab } from "@/components/TabBar";
import Conversation from "@/components/Conversation";
import LoadGamePanel, { LoadedGamePayload } from "@/components/LoadGamePanel";
import PersonalReview from "@/components/PersonalReview";
import ProfileDashboard from "@/components/ProfileDashboard/ProfileDashboard";
import ProfileSetupModal, { ProfilePreferences } from "@/components/ProfileSetupModal";
import AuthModal from "@/components/AuthModal";
import { fetchProfileOverview, fetchProfileStats, saveProfilePreferences } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

import "@/styles/chatUI.css";
import "./MobileShell.css";

const INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

interface MobileShellProps {
  children: (actions: { openPersonalReview: () => void }) => React.ReactNode;
  analyticsRef?: React.RefObject<HTMLDivElement>;
}

type MinimalMessage = {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
};

const normalizeProfilePreferences = (
  raw?: { accounts?: Array<{ platform: "chesscom" | "lichess"; username: string }> ; time_controls?: string[] | null; timeControls?: string[] | null; }
): ProfilePreferences | null => {
  if (!raw) {
    return null;
  }

  let accountsArray = raw.accounts;
  if (!Array.isArray(accountsArray)) {
    accountsArray = [];
  }

  const allowed = new Set(["bullet", "blitz", "rapid"]);
  const accounts = accountsArray.map((acc, index) => {
    const platform = typeof acc === "string" ? acc : acc?.platform || "chesscom";
    const username = typeof acc === "string" ? "" : acc?.username || "";
    return {
      id: `${platform}-${username || index}-${index}`,
      platform: platform as "chesscom" | "lichess",
      username,
    };
  });

  const timeControls = (raw.time_controls ?? raw.timeControls ?? [])
    .map((tc) => String(tc).toLowerCase())
    .filter((tc): tc is "bullet" | "blitz" | "rapid" => allowed.has(tc));

  return {
    accounts,
    timeControls: timeControls.length
      ? timeControls
      : (["blitz", "rapid"] as Array<"bullet" | "blitz" | "rapid">),
  };
};

export default function MobileShell({ children, analyticsRef }: MobileShellProps) {
  const { user, loading: authLoading, signOut } = useAuth();
  const authUserEmail = user?.email ?? null;
  const authUserName =
    (user?.user_metadata?.username as string | undefined) ||
    (user?.user_metadata?.full_name as string | undefined) ||
    (user?.user_metadata?.name as string | undefined) ||
    (authUserEmail ? authUserEmail.split("@")[0] : null);

  const [showHistory, setShowHistory] = useState(false);
  const [showPersonalReview, setShowPersonalReview] = useState(false);
  const [showProfileDashboard, setShowProfileDashboard] = useState(false);
  const [showProfileSetupModal, setShowProfileSetupModal] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showLoadGame, setShowLoadGame] = useState(false);
  const [loadGameInitialTab, setLoadGameInitialTab] = useState<
    "pgn" | "fen" | "link" | "lookup" | "photo"
  >("pgn");
  const [showRequestOptions, setShowRequestOptions] = useState(false);

  const [messages, setMessages] = useState<MinimalMessage[]>([
    {
      role: "assistant",
      content: "Ask about your recent games, openings, or performance trends.",
    },
  ]);

  const [fen, setFen] = useState(INITIAL_FEN);
  const [pgn, setPgn] = useState("");
  const [boardDockOpen, setBoardDockOpen] = useState(false);
  const [boardOrientation, setBoardOrientation] = useState<"white" | "black">("white");

  const [profilePreferences, setProfilePreferences] = useState<ProfilePreferences | null>(null);
  const [profileStatus, setProfileStatus] = useState<any | null>(null);
  const [profileOverview, setProfileOverview] = useState<any | null>(null);
  const [profileStats, setProfileStats] = useState<any | null>(null);
  const refreshInProgressRef = useRef(false);

  const tabs: BoardTab[] = useMemo(
    () => [
      {
        id: "board-1",
        name: "Board",
        fen,
        pgn,
        isAnalyzing: false,
        hasUnread: false,
        isModified: false,
        createdAt: Date.now(),
      },
    ],
    [fen, pgn]
  );

  const handleSendMessage = (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "Thanks! I can help break that down." },
    ]);
  };

  const handleMove = (from: string, to: string, promotion?: string) => {
    const nextGame = new Chess(fen);
    const move = nextGame.move({ from, to, promotion });
    if (!move) return;
    setFen(nextGame.fen());
    setPgn(nextGame.pgn());
  };

  const handleLoadGame = (payload: LoadedGamePayload) => {
    if (payload.fen) {
      setFen(payload.fen);
    }
    if (payload.pgn) {
      setPgn(payload.pgn);
    }
    if (payload.orientation) {
      setBoardOrientation(payload.orientation);
    }
  };

  const refreshProfileData = useCallback(async () => {
    if (!user || refreshInProgressRef.current) return;
    refreshInProgressRef.current = true;
    try {
      const overview = await fetchProfileOverview(user.id);
      setProfileOverview(overview);
      setProfileStatus(overview.status || null);
      const normalized = normalizeProfilePreferences(overview.preferences as any);
      if (normalized) {
        setProfilePreferences(normalized);
        setShowProfileSetupModal(false);
      } else {
        setProfilePreferences(null);
        setShowProfileSetupModal(true);
      }
      const statsResponse = await fetchProfileStats(user.id);
      setProfileStats(statsResponse.stats || null);
    } catch (error) {
      console.warn("[MobileShell] Failed to refresh profile data:", error);
    } finally {
      refreshInProgressRef.current = false;
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setProfilePreferences(null);
      setProfileOverview(null);
      setProfileStatus(null);
      setProfileStats(null);
      setShowProfileSetupModal(false);
      return;
    }
    refreshProfileData();
    const interval = setInterval(refreshProfileData, 15000);
    return () => clearInterval(interval);
  }, [user, refreshProfileData]);

  useEffect(() => {
    if (user && showAuthModal) {
      setShowAuthModal(false);
    }
  }, [user, showAuthModal]);

  const handleSaveProfilePreferences = async (prefs: ProfilePreferences) => {
    if (!user) return;
    const overview = await saveProfilePreferences({
      userId: user.id,
      accounts: prefs.accounts.map(({ platform, username }) => ({ platform, username })),
      timeControls: prefs.timeControls,
    });
    setProfileOverview(overview);
    setProfileStatus(overview.status || null);
    setProfilePreferences(normalizeProfilePreferences(overview.preferences as any) ?? prefs);
    setShowProfileSetupModal(false);
  };

  const handleAuthSignOut = async () => {
    try {
      await signOut();
    } catch (err) {
      console.error("Sign out failed", err);
    }
  };

  const handleSwitchAccount = async () => {
    try {
      await signOut();
    } finally {
      setShowAuthModal(true);
    }
  };

  const handleOpenAnalytics = () => {
    const prefersReduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)"
    )?.matches;
    analyticsRef?.current?.scrollIntoView({
      behavior: prefersReduced ? "auto" : "smooth",
      block: "start",
    });
  };

  return (
    <div className="v2-mobile-shell" data-theme="night">
      <TopBar
        onToggleHistory={() => setShowHistory(!showHistory)}
        onOpenAnalytics={analyticsRef ? handleOpenAnalytics : undefined}
        onSignIn={() => setShowAuthModal(true)}
        onSignOut={handleAuthSignOut}
        onSwitchAccount={handleSwitchAccount}
        userEmail={authUserEmail}
        userName={authUserName}
        authLoading={authLoading}
      />

      {showAuthModal && !user && <AuthModal onClose={() => setShowAuthModal(false)} />}

      <main
        className={`chat-layout ${boardDockOpen ? "with-board" : ""} mobile-mode v2-mobile-layout`}
      >
        {boardDockOpen && (
          <div className="layout-column board-column">
            <TabBar
              tabs={tabs}
              activeTabId={tabs[0].id}
              onTabSelect={() => {}}
              onTabClose={() => {}}
              onTabRename={() => {}}
              onTabDuplicate={() => {}}
              onNewTab={() => {}}
              onHideBoard={() => setBoardDockOpen(false)}
              maxTabs={1}
            />
            <BoardDock
              fen={fen}
              pgn={pgn}
              arrows={[]}
              highlights={[]}
              onMove={handleMove}
              orientation={boardOrientation}
              onFlipBoard={() =>
                setBoardOrientation((prev) => (prev === "white" ? "black" : "white"))
              }
              onLoadGame={() => setShowLoadGame(true)}
              onHideBoard={() => setBoardDockOpen(false)}
            />
          </div>
        )}
        <div className="layout-column chat-column">
          {children({ openPersonalReview: () => setShowPersonalReview(true) })}
          <Conversation
            messages={messages as any}
            onToggleBoard={!boardDockOpen ? () => setBoardDockOpen(true) : undefined}
            isBoardOpen={boardDockOpen}
            onLoadGame={!boardDockOpen ? () => setShowLoadGame(true) : undefined}
            currentFEN={fen}
            isMobileMode
            fen={fen}
            pgn={pgn}
            arrows={[]}
            highlights={[]}
            boardOrientation={boardOrientation}
          />
        </div>
      </main>

      <BottomComposer
        onSend={handleSendMessage}
        onOpenOptions={() => setShowRequestOptions(true)}
      />

      <HistoryCurtain
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onSelectThread={() => {}}
        currentThreadId={null}
        profilePreferences={profilePreferences}
        profileStatus={profileStatus}
        profileHighlights={profileOverview?.highlights}
        profileGames={profileOverview?.games}
        profileStats={profileStats}
        onEditProfileSetup={() => setShowProfileSetupModal(true)}
        onRefreshProfile={refreshProfileData}
        onOpenProfileDashboard={() => setShowProfileDashboard(true)}
        onOpenPersonalReview={() => setShowPersonalReview(true)}
        userId={user?.id}
      />

      {showLoadGame && (
        <LoadGamePanel
          onLoad={(payload) => {
            handleLoadGame(payload);
            setShowLoadGame(false);
          }}
          onClose={() => setShowLoadGame(false)}
          initialTab={loadGameInitialTab}
        />
      )}

      {showPersonalReview && (
        <PersonalReview onClose={() => setShowPersonalReview(false)} />
      )}

      {showProfileDashboard && (
        <ProfileDashboard
          onClose={() => setShowProfileDashboard(false)}
          initialTab="overview"
        />
      )}

      {user && (
        <ProfileSetupModal
          open={showProfileSetupModal}
          onClose={() => setShowProfileSetupModal(false)}
          onSave={handleSaveProfilePreferences}
          initialData={profilePreferences}
        />
      )}

      {showRequestOptions && (
        <div className="request-options-overlay" role="dialog" aria-modal="true">
          <div className="request-options-modal">
            <h3>Manual Request</h3>
            <p>Select a request to run without the LLM.</p>
            <div className="request-options-buttons">
              <button
                type="button"
                onClick={() => {
                  setShowRequestOptions(false);
                  setLoadGameInitialTab("photo");
                  setShowLoadGame(true);
                }}
              >
                Import Image
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowRequestOptions(false);
                  setLoadGameInitialTab("pgn");
                  setShowLoadGame(true);
                }}
              >
                Load Game
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowRequestOptions(false);
                  setShowPersonalReview(true);
                }}
              >
                Open Personal Review
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowRequestOptions(false);
                  setShowProfileDashboard(true);
                }}
              >
                Open Profile Dashboard
              </button>
              {!boardDockOpen && (
                <button
                  type="button"
                  onClick={() => {
                    setShowRequestOptions(false);
                    setBoardDockOpen(true);
                  }}
                >
                  Show Chessboard
                </button>
              )}
              <button type="button" onClick={() => setShowRequestOptions(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

