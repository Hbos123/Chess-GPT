"use client";

import { useState, type MouseEvent } from 'react';
import { signInWithGoogle, signInWithApple, signInWithPassword, signUpWithPassword } from '@/lib/supabase';

interface AuthModalProps {
  onClose?: () => void;
}

export default function AuthModal({ onClose }: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [method, setMethod] = useState<'password' | 'oauth'>('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const friendlyAuthError = (raw: string | undefined | null) => {
    if (!raw) return 'Something went wrong. Please try again.';
    if (/provider is not enabled/i.test(raw)) {
      return 'That sign-in provider is disabled. Enable it in Supabase Auth → Providers or use email/password.';
    }
    if (/refresh_token_hmac_key/i.test(raw)) {
      return 'Supabase project is missing the Refresh Token HMAC key. In Supabase → Auth → Settings → URL Configuration add REFRESH_TOKEN_HMAC_KEY, then refresh this page.';
    }
    return raw;
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError('');
    
    try {
      const { error } = await signInWithGoogle();
      if (error) {
        setError(friendlyAuthError(error.message));
      }
    } finally {
      setLoading(false);
    }
    // Redirect will happen automatically
  };

  const handleAppleSignIn = async () => {
    setLoading(true);
    setError('');
    
    try {
      const { error } = await signInWithApple();
      if (error) {
        setError(friendlyAuthError(error.message));
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordAuth = async () => {
    if (!email || !password) {
      setError('Please enter email and password');
      return;
    }

    if (mode === 'signup' && !username) {
      setError('Please enter a username');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      let result;
      if (mode === 'signup') {
        result = await signUpWithPassword(email, password, username);
      } else {
        result = await signInWithPassword(email, password);
      }
      
      if (result.error) {
        setError(friendlyAuthError(result.error.message));
      } else if (mode === 'signup') {
        setSuccess('Account created! Check your email to verify.');
      } else {
        onClose?.();
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOverlayClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose?.();
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={handleOverlayClick}>
      <div className="auth-modal">
        <div className="auth-header">
          <h2>♟️ Welcome to Chess GPT</h2>
          <p>Sign in to save your progress and access your data anywhere</p>
          {onClose && (
            <button className="auth-close-btn" onClick={onClose} aria-label="Close sign in dialog">
              ×
            </button>
          )}
        </div>

        <div className="auth-content">
          {/* Mode toggle */}
          <div className="auth-mode-toggle">
            <button
              className={`mode-btn ${mode === 'signin' ? 'active' : ''}`}
              onClick={() => setMode('signin')}
            >
              Sign In
            </button>
            <button
              className={`mode-btn ${mode === 'signup' ? 'active' : ''}`}
              onClick={() => setMode('signup')}
            >
              Sign Up
            </button>
          </div>

          <div className="auth-method-toggle">
            <button
              className={`method-btn ${method === 'password' ? 'active' : ''}`}
              onClick={() => setMethod('password')}
            >
              Email + password
            </button>
            <button
              className={`method-btn ${method === 'oauth' ? 'active' : ''}`}
              onClick={() => setMethod('oauth')}
            >
              Apple / Google
            </button>
          </div>

          {/* Email + Password */}
          {method === 'password' && (
            <div className="auth-section">
              {mode === 'signup' && (
                <input
                  type="text"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="auth-input"
                />
              )}
              
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="auth-input"
              />
              
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="auth-input"
              />
              
              <button
                className="auth-submit-btn"
                onClick={handlePasswordAuth}
                disabled={loading}
              >
                {loading ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
              </button>
            </div>
          )}

          {/* OAuth */}
          {method === 'oauth' && (
            <div className="auth-section">
              <button
                className="apple-btn"
                onClick={handleAppleSignIn}
                disabled={loading}
              >
                <svg className="apple-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M16.365 1.43c0 1.14-.416 2.097-1.248 2.871-.999.95-2.168 1.535-3.01 1.446-.102-.828.341-1.78 1.215-2.663.442-.46 1.001-.852 1.677-1.176.676-.326 1.296-.503 1.893-.521.032.014.059.022.073.043.023.033.023.071.023.111-.01.125-.023.25-.023.37zm3.616 17.279c-.543 1.177-1.18 2.226-1.915 3.146-.736.912-1.404 1.368-2.004 1.368-.445 0-1.002-.267-1.668-.802-.669-.534-1.284-.806-1.843-.806-.593 0-1.23.267-1.915.806-.688.535-1.229.804-1.633.804-.557 0-1.159-.432-1.81-1.297-.651-.867-1.258-1.938-1.82-3.217-.596-1.373-.895-2.698-.895-3.974 0-1.466.32-2.623.961-3.47.64-.848 1.479-1.276 2.513-1.29.495 0 1.153.232 1.97.697.816.466 1.34.699 1.57.699.171 0 .743-.284 1.717-.85.921-.528 1.7-.748 2.341-.66 1.729.139 2.984.934 3.768 2.386-1.498.908-2.245 2.18-2.245 3.817.01 1.273.386 2.336 1.128 3.191z" fill="currentColor"/>
                </svg>
                Continue with Apple
              </button>
              <button
                className="google-btn"
                onClick={handleGoogleSignIn}
                disabled={loading}
              >
                <svg className="google-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>
              <p className="provider-hint">
                Providers disabled? Enable them in Supabase Auth → Providers.
              </p>
            </div>
          )}

          {/* Error/Success messages */}
          {error && (
            <div className="auth-error">
              ⚠️ {error}
            </div>
          )}
          
          {success && (
            <div className="auth-success">
              ✅ {success}
            </div>
          )}
        </div>

        <div className="auth-footer">
          <p>By signing in, you agree to our Terms of Service and Privacy Policy</p>
        </div>
      </div>
    </div>
  );
}

