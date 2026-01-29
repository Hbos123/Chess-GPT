"use client";

import { type MouseEvent } from 'react';

interface TokenLimitModalProps {
  onClose: () => void;
  limitInfo: {
    type: 'message_limit' | 'token_limit';
    message: string;
    info: {
      used?: number;
      limit?: number;
      next_step?: string;
      tier_id?: string;
      messages?: {
        used: number;
        limit: number | string;
        remaining?: number | string;
      };
      tokens?: {
        used: number;
        limit: number;
        remaining?: number;
      };
    };
  };
  onOpenProfile?: () => void;
  isLoggedIn?: boolean; // Whether user is logged in
}

export default function TokenLimitModal({ onClose, limitInfo, onOpenProfile, isLoggedIn = false }: TokenLimitModalProps) {
  const handleBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const getUpgradeMessage = () => {
    const tierId = limitInfo.info.tier_id || 'unpaid';
    const isMessageLimit = limitInfo.type === 'message_limit';
    
    // Unlogged user
    if (!isLoggedIn) {
      return {
        title: 'Usage limit reached',
        message: 'Make an account with us to keep on trying chesster out!',
        action: 'Sign In / Create Account',
        actionUrl: '/auth',
        useModal: false,
        showUsage: false // Don't show usage for unsigned-in
      };
    }
    
    // Signed in unpaid user
    if (tierId === 'unpaid') {
      return {
        title: isMessageLimit ? 'Daily message limit reached' : 'Daily token limit reached',
        message: isMessageLimit
          ? 'Upgrade to Lite to keep chatting (token-based limits) and unlock tools.'
          : 'Upgrade to Lite for more daily tokens and unlock tools.',
        action: 'Upgrade to Lite',
        actionUrl: null,
        useModal: true,
        showUsage: false // Don't show usage for unpaid tier
      };
    }
    
    // Lite tier
    if (tierId === 'lite') {
      return {
        title: 'Lite limit reached',
        message: 'Move up to Starter for a bigger daily token budget and more features.',
        action: 'Upgrade to Starter',
        actionUrl: null,
        useModal: true,
        showUsage: true
      };
    }
    
    // Starter tier
    if (tierId === 'starter') {
      return {
        title: 'Starter limit reached',
        message: 'Upgrade to Full for the biggest daily token budget and everything unlocked.',
        action: 'Upgrade to Full',
        actionUrl: null,
        useModal: true,
        showUsage: true
      };
    }
    
    // Default fallback
    return {
      title: 'Limit Reached',
      message: "You've reached your daily limit. Try again tomorrow or upgrade for more.",
      action: 'View Plans',
      actionUrl: null,
      useModal: true,
      showUsage: true
    };
  };

  const upgradeInfo = getUpgradeMessage();
  // Only show usage for paid tiers (lite, starter, full)
  const usage = upgradeInfo.showUsage && (
    limitInfo.type === "message_limit" && limitInfo.info.messages && typeof limitInfo.info.messages.limit === "number"
      ? `${limitInfo.info.messages.used ?? 0} / ${limitInfo.info.messages.limit}`
      : limitInfo.type === "token_limit" && limitInfo.info.tokens
        ? `${limitInfo.info.tokens.used ?? 0} / ${limitInfo.info.tokens.limit ?? 0}`
        : (limitInfo.info.used !== undefined && limitInfo.info.limit !== undefined
          ? `${limitInfo.info.used} / ${limitInfo.info.limit}`
          : null)
  ) || null;

  return (
    <div
      className="modal-backdrop"
      onClick={handleBackdropClick}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
    >
      <div
        className="modal-content"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '12px',
          padding: '24px',
          maxWidth: '500px',
          width: '90%',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
          border: '1px solid var(--border-color)',
        }}
      >
        <div style={{ marginBottom: '20px' }}>
          <h2 style={{ margin: '0 0 12px 0', fontSize: '20px', fontWeight: 600 }}>
            {upgradeInfo.title}
          </h2>
          <p style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            {upgradeInfo.message}
          </p>
          {usage && (
            <div style={{
              padding: '12px',
              backgroundColor: 'var(--bg-secondary)',
              borderRadius: '8px',
              marginBottom: '16px',
              fontSize: '14px',
            }}>
              <strong>Usage:</strong> {usage}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '10px 20px',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            Close
          </button>
          {(upgradeInfo.actionUrl || upgradeInfo.useModal) && (
            <button
              onClick={() => {
                onClose();
                if (upgradeInfo.useModal && onOpenProfile) {
                  // Open ProfileDashboard modal
                  onOpenProfile();
                } else if (upgradeInfo.actionUrl) {
                  // Navigate to URL (for sign in)
                  window.location.href = upgradeInfo.actionUrl;
                }
              }}
              style={{
                padding: '10px 20px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: 'var(--accent-color)',
                color: 'white',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              {upgradeInfo.action}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
