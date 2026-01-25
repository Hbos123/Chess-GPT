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
      return 'This sign-in provider is not enabled. To enable it:\n\n1. Go to your Supabase Dashboard\n2. Navigate to Authentication → Providers\n3. Enable Google and/or Apple\n4. Configure OAuth credentials\n5. Add redirect URL: ' + window.location.origin + '/auth/callback\n\nOr use email/password sign-in instead.';
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

  const handleAppleSignIn = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const result = await signInWithApple();
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
        setError('Failed to start Apple sign-in. Please try again or use email/password.');
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

