import { useEffect, useRef, useState } from "react";

interface TopBarProps {
  onToggleHistory: () => void;
  onOpenAnalytics?: () => void;
  onSignIn?: () => void;
  onSignOut?: () => Promise<void> | void;
  onSwitchAccount?: () => Promise<void> | void;
  userEmail?: string | null;
  userName?: string | null;
  authLoading?: boolean;
}

export default function TopBar({
  onToggleHistory,
  onOpenAnalytics,
  onSignIn,
  onSignOut,
  onSwitchAccount,
  userEmail,
  userName,
  authLoading,
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDocPointerDown = (e: MouseEvent | PointerEvent) => {
      const el = menuRef.current;
      if (!el) return;
      if (e.target instanceof Node && el.contains(e.target)) return;
      setMenuOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onDocPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const initials = userName?.[0]?.toUpperCase() || userEmail?.[0]?.toUpperCase() || 'U';
  const greetingName = userName || userEmail || 'Player';

  return (
    <div className="top-bar">
      <div className="top-bar-left">
        <button 
          className="history-toggle"
          onClick={onToggleHistory}
          aria-label="Toggle chat history"
        >
          <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        {onOpenAnalytics && (
          <button
            type="button"
            className="topbar-shortcut"
            onClick={onOpenAnalytics}
            aria-label="Open analytics overview"
          >
            Analytics
          </button>
        )}
      </div>

      <div className="wordmark">Chesster AI</div>

      <div className="top-bar-actions">
        {userEmail ? (
          <div className="user-menu" ref={menuRef}>
            <button
              className="user-avatar"
              aria-label={`Signed in as ${greetingName}`}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
              type="button"
            >
              <div className="user-avatar-initial">{initials}</div>
              <div className="user-greeting">
                <span className="user-greeting-line">Hi {greetingName}</span>
              </div>
            </button>
            {menuOpen && (
              <div className="user-dropdown" role="menu">
                <div className="user-dropdown-header">
                  <div className="user-dropdown-name">{greetingName}</div>
                  <div className="user-email-label">{userEmail}</div>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    setMenuOpen(false);
                    await onSwitchAccount?.();
                  }}
                >
                  Change account
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    setMenuOpen(false);
                    await onSignOut?.();
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            className="auth-button"
            onClick={onSignIn}
            // Never disable sign-in just because initial auth hydration is in-flight.
            // If Supabase calls are slow/blocked, we still want users to be able to retry sign-in.
            disabled={false}
            aria-busy={!!authLoading}
          >
            Sign in
          </button>
        )}
      </div>
    </div>
  );
}

