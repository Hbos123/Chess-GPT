"use client";

import { useState, useEffect } from "react";

export type ProfileAccount = {
  id: string;
  platform: "chesscom" | "lichess";
  username: string;
};

export type ProfilePreferences = {
  accounts: ProfileAccount[];
  timeControls: Array<"bullet" | "blitz" | "rapid">;
};

interface ProfileSetupModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (prefs: ProfilePreferences) => Promise<void> | void;
  initialData?: ProfilePreferences | null;
}

const TIME_CONTROL_OPTIONS: Array<"bullet" | "blitz" | "rapid"> = [
  "bullet",
  "blitz",
  "rapid",
];

const createAccountId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `acct-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const MAX_ACCOUNTS = 4;

export default function ProfileSetupModal({
  open,
  onClose,
  onSave,
  initialData,
}: ProfileSetupModalProps) {
  const [accounts, setAccounts] = useState<ProfileAccount[]>([]);
  const [timeControls, setTimeControls] = useState<Array<"bullet" | "blitz" | "rapid">>([
    "blitz",
    "rapid",
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (initialData?.accounts?.length) {
      setAccounts(initialData.accounts);
    } else {
      setAccounts([
        {
          id: createAccountId(),
          platform: "chesscom",
          username: "",
        },
      ]);
    }

    if (initialData?.timeControls?.length) {
      setTimeControls(initialData.timeControls);
    } else {
      setTimeControls(["blitz", "rapid"]);
    }
    setErrorMessage(null);
  }, [initialData, open]);

  if (!open) {
    return null;
  }

  const handleAccountChange = (
    id: string,
    field: "platform" | "username",
    value: string
  ) => {
    setAccounts((prev) =>
    prev.map((account) =>
        account.id === id ? { ...account, [field]: value } : account
      )
    );
  };

  const handleAddAccount = () => {
    if (accounts.length >= MAX_ACCOUNTS) return;
    setAccounts((prev) => [
      ...prev,
      { id: createAccountId(), platform: "chesscom", username: "" },
    ]);
  };

  const handleRemoveAccount = (id: string) => {
    if (accounts.length === 1) return;
    setAccounts((prev) => prev.filter((account) => account.id !== id));
  };

  const handleToggleTimeControl = (value: "bullet" | "blitz" | "rapid") => {
    setTimeControls((prev) =>
      prev.includes(value) ? prev.filter((tc) => tc !== value) : [...prev, value]
    );
  };

  const handleSubmit = async () => {
    setErrorMessage(null);
    try {
      setSubmitting(true);
      const sanitizedAccounts = accounts.filter((acc) => acc.username.trim().length > 0);
      await onSave({
        accounts: sanitizedAccounts.length ? sanitizedAccounts : accounts,
        timeControls: timeControls.length ? timeControls : ["blitz", "rapid"],
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to save preferences. Please try again.";
      setErrorMessage(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="profile-setup-overlay" role="dialog" aria-modal="true">
      <div className="profile-setup-modal">
        <header>
          <h2>Set up your profile indexing</h2>
          <p>
            Linking your accounts and preferred time controls allows Chesster to
            personalise feedback, highlight trends, and craft training plans from
            your recent games. You can revisit this later in the Personal dashboard.
          </p>
        </header>

        <section className="profile-section">
          <div className="section-head">
            <h3>Chess accounts</h3>
            <button
              type="button"
              onClick={handleAddAccount}
              disabled={accounts.length >= MAX_ACCOUNTS}
            >
              + Add account
            </button>
          </div>
          <div className="profile-account-list">
            {accounts.map((account) => (
              <div key={account.id} className="profile-account-row">
                <select
                  value={account.platform}
                  onChange={(e) =>
                    handleAccountChange(
                      account.id,
                      "platform",
                      e.target.value as ProfileAccount["platform"]
                    )
                  }
                >
                  <option value="chesscom">Chess.com</option>
                  <option value="lichess">Lichess</option>
                </select>
                <input
                  type="text"
                  placeholder={
                    account.platform === "chesscom"
                      ? "Chess.com username"
                      : "Lichess username"
                  }
                  value={account.username}
                  onChange={(e) =>
                    handleAccountChange(account.id, "username", e.target.value)
                  }
                />
                <button
                  type="button"
                  className="ghost"
                  onClick={() => handleRemoveAccount(account.id)}
                  disabled={accounts.length === 1}
                  aria-label="Remove account"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="profile-section">
          <h3>Time controls to index</h3>
              <div className="time-control-grid">
                {TIME_CONTROL_OPTIONS.map((tc) => (
                  <button
                    key={tc}
                    type="button"
                    className={`time-control-chip ${
                      timeControls.includes(tc) ? "selected" : ""
                    }`}
                    onClick={() => handleToggleTimeControl(tc)}
                  >
                    {tc.charAt(0).toUpperCase() + tc.slice(1)}
                  </button>
                ))}
              </div>
        </section>

        {errorMessage && <div className="profile-setup-error">⚠️ {errorMessage}</div>}

        <footer className="profile-actions">
          <button type="button" className="ghost" onClick={onClose}>
            Skip for now
          </button>
          <button
            type="button"
            className="primary"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Save preferences"}
          </button>
        </footer>
      </div>
    </div>
  );
}

