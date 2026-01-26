'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function SettingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  useEffect(() => {
    // Redirect to home page - settings will be opened via query params
    const success = searchParams.get('success');
    const canceled = searchParams.get('canceled');
    
    // Build redirect URL with settings param
    const params = new URLSearchParams();
    if (success === 'true') {
      params.set('settings', 'open');
      params.set('checkout', 'success');
    } else if (canceled === 'true') {
      params.set('settings', 'open');
      params.set('checkout', 'canceled');
    } else {
      params.set('settings', 'open');
    }
    
    router.replace(`/?${params.toString()}`);
  }, [router, searchParams]);
  
  // Show loading state while redirecting
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: 'var(--bg-primary)',
      color: 'var(--text-primary)'
    }}>
      <div>Redirecting to settings...</div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--bg-primary)',
        color: 'var(--text-primary)'
      }}>
        <div>Loading...</div>
      </div>
    }>
      <SettingsPageContent />
    </Suspense>
  );
}
