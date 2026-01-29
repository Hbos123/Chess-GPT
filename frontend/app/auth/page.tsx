"use client";

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import AuthModal from '@/components/AuthModal';
import { useAuth } from '@/contexts/AuthContext';

export default function AuthPage() {
  const router = useRouter();
  const { user } = useAuth();

  // If user is already logged in, redirect to app
  useEffect(() => {
    if (user) {
      router.push('/app');
    }
  }, [user, router]);

  const handleClose = () => {
    // Redirect to app after successful auth
    router.push('/app');
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--bg-primary, #1a1a1a)',
      padding: '20px'
    }}>
      <AuthModal onClose={handleClose} />
    </div>
  );
}
