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
    };
  };
  onOpenProfile?: () => void;
}

export default function TokenLimitModal({ onClose, limitInfo, onOpenProfile }: TokenLimitModalProps) {
  const handleBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const getUpgradeMessage = () => {
    const nextStep = limitInfo.info.next_step;
    const tierId = limitInfo.info.tier_id || 'unpaid';
    
    if (nextStep === 'sign_in') {
      return {
        title: 'Sign In Required',
        message: 'Sign in to get more daily messages and tokens.',
        action: 'Sign In',
        actionUrl: '/auth',
        useModal: false
      };
    } else if (nextStep === 'upgrade_lite') {
      return {
        title: 'Upgrade to Lite',
        message: 'Upgrade to Lite tier for 15 messages/day and 43k tokens/day.',
        action: 'Upgrade',
        actionUrl: null,
        useModal: true
      };
    } else if (nextStep === 'upgrade') {
      return {
        title: 'Upgrade Your Plan',
        message: 'Upgrade your plan to get more daily messages and tokens.',
        action: 'Upgrade',
        actionUrl: null,
        useModal: true
      };
    } else {
      return {
        title: 'Limit Reached',
        message: 'You\'ve reached your daily limit. Try again tomorrow or upgrade for more.',
        action: 'View Plans',
        actionUrl: null,
        useModal: true
      };
    }
  };

  const upgradeInfo = getUpgradeMessage();
  const usage = limitInfo.info.used !== undefined && limitInfo.info.limit !== undefined
    ? `${limitInfo.info.used} / ${limitInfo.info.limit}`
    : null;

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
            {limitInfo.message}
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
