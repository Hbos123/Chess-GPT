interface TopBarProps {
  onToggleHistory: () => void;
  onSignIn?: () => void;
  onSignOut?: () => Promise<void> | void;
  onSwitchAccount?: () => Promise<void> | void;
  userEmail?: string | null;
  userName?: string | null;
  authLoading?: boolean;
}

export default function TopBar({
  onToggleHistory,
  onSignIn,
  onSignOut,
  onSwitchAccount,
  userEmail,
  userName,
  authLoading,
}: TopBarProps) {
  const initials = userName?.[0]?.toUpperCase() || userEmail?.[0]?.toUpperCase() || 'U';
  const greetingName = userName || userEmail || 'Player';

  return (
    <div className="top-bar">
      <button 
        className="history-toggle"
        onClick={onToggleHistory}
        aria-label="Toggle chat history"
      >
        <svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>

      <div className="wordmark">Chesster AI</div>

      <div className="top-bar-actions">
        {userEmail ? (
          <div className="user-menu">
            <button className="user-avatar" aria-label={`Signed in as ${greetingName}`}>
              <div className="user-avatar-initial">{initials}</div>
              <div className="user-greeting">
                <span className="user-greeting-line">Hi {greetingName}</span>
              </div>
            </button>
            <div className="user-dropdown">
              <div className="user-dropdown-header">
                <div className="user-dropdown-name">{greetingName}</div>
                <div className="user-email-label">{userEmail}</div>
              </div>
              <button onClick={() => onSwitchAccount?.()}>Change account</button>
              <button onClick={() => onSignOut?.()}>Sign out</button>
            </div>
          </div>
        ) : (
          <button
            className="auth-button"
            onClick={onSignIn}
            disabled={authLoading}
          >
            {authLoading ? 'Loading...' : 'Sign in'}
          </button>
        )}
      </div>
    </div>
  );
}

