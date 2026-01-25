"use client";

import { useState, type MouseEvent } from 'react';
import { signInWithGoogle, signInWithPassword, signUpWithPassword } from '@/lib/supabase';

interface AuthModalProps {
  onClose?: () => void;
}

export default function AuthModal({ onClose }: AuthModalProps) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const friendlyAuthError = (error: any): string => {
    // Handle different error formats
    let errorMessage = '';
    
    // Check if it's a string
    if (typeof error === 'string') {
      errorMessage = error;
    }
    // Check if it's an error object with message
    else if (error?.message) {
      errorMessage = error.message;
    }
    // Check if it's a JSON response with msg field
    else if (error?.msg) {
      errorMessage = error.msg;
    }
    // Check if it's a JSON response with error field
    else if (error?.error) {
      errorMessage = typeof error.error === 'string' ? error.error : error.error.message || JSON.stringify(error.error);
    }
    // Try to parse as JSON string
    else if (typeof error === 'object') {
      try {
        const jsonStr = JSON.stringify(error);
        const parsed = JSON.parse(jsonStr);
        errorMessage = parsed.msg || parsed.message || parsed.error || jsonStr;
      } catch {
        errorMessage = 'Something went wrong. Please try again.';
      }
    }
    
    if (!errorMessage) {
      return 'Something went wrong. Please try again.';
    }
    
    // Normalize error message
    const normalized = errorMessage.toLowerCase();
    
    // Provider not enabled errors
    if (normalized.includes('provider is not enabled') || 
        normalized.includes('unsupported provider') ||
        normalized.includes('validation_failed')) {
      return 'Google sign-in is not enabled. To enable it:\n\n1. Go to your Supabase Dashboard\n2. Navigate to Authentication → Providers\n3. Enable Google\n4. Configure OAuth credentials\n5. Add redirect URL: ' + window.location.origin + '/auth/callback\n\nOr use email/password sign-in instead.';
    }
    
    // Refresh token errors
    if (normalized.includes('refresh_token_hmac_key')) {
      return 'Supabase project is missing the Refresh Token HMAC key. In Supabase → Auth → Settings → URL Configuration add REFRESH_TOKEN_HMAC_KEY, then refresh this page.';
    }
    
    // Email verification errors
    if (normalized.includes('email not confirmed') || normalized.includes('email_not_confirmed')) {
      return 'Please verify your email address. Check your inbox for a verification link.';
    }
    
    // Invalid credentials
    if (normalized.includes('invalid') && normalized.includes('credential')) {
      return 'Invalid email or password. Please try again.';
    }
    
    // User already exists
    if (normalized.includes('user already registered') || normalized.includes('already registered')) {
      return 'An account with this email already exists. Try signing in instead.';
    }
    
    return errorMessage;
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const result = await signInWithGoogle();
      if (result.error) {
        // Handle different error formats
        const errorObj = result.error;
        let errorMsg = '';
        
        // Check if error has a message property
        if (errorObj?.message) {
          errorMsg = friendlyAuthError(errorObj);
        }
        // Check if error is a JSON response
        else if (typeof errorObj === 'object') {
          errorMsg = friendlyAuthError(errorObj);
        }
        // Try to parse as string
        else {
          errorMsg = friendlyAuthError(String(errorObj));
        }
        
        setError(errorMsg);
      }
      // If no error and no URL, that's also an error
      else if (!result.data?.url) {
        setError('Failed to start Google sign-in. Please try again or use email/password.');
      }
      // Otherwise, redirect will happen automatically
    } catch (err: any) {
      setError(friendlyAuthError(err));
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

          {/* Email + Password Form */}
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

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', margin: '20px 0', gap: '12px' }}>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
            <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>or</span>
            <div style={{ flex: 1, height: '1px', background: 'var(--border-color)' }} />
          </div>

          {/* Google Sign In */}
          <div className="auth-section">
            <button
              className="google-btn"
              onClick={handleGoogleSignIn}
              disabled={loading}
              style={{ width: '100%' }}
            >
              <svg className="google-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </button>
          </div>

          {/* Error/Success messages */}
          {error && (
            <div className="auth-error" style={{ whiteSpace: 'pre-line' }}>
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

