/**
 * Console helper to reset tokens to zero for testing
 * 
 * Usage in browser console:
 *   await resetMyTokens()
 * 
 * Or if you have the user ID:
 *   await resetMyTokens('a1652893-3bd8-46b2-a5aa-c28609c84f01')
 */

"use client";

import { getBackendBase } from './backendBase';
import { supabase } from './supabase';

export async function resetMyTokens(userId?: string): Promise<void> {
  try {
    // Get user ID if not provided
    if (!userId) {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        console.error('❌ Not logged in. Please log in first.');
        return;
      }
      userId = user.id;
      console.log(`✅ Detected logged-in user: ${userId}`);
    }

    console.log(`🔄 Resetting tokens for user: ${userId}...`);
    
    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/admin/reset-tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error(`❌ Error: ${response.status} - ${error}`);
      return;
    }

    const result = await response.json();
    console.log('✅ Tokens reset!', result);
    console.log(`   ${result.message || 'Tokens reset to 0'}`);
    
  } catch (error) {
    console.error('❌ Error resetting tokens:', error);
  }
}

// Make it available on window for easy console access
if (typeof window !== 'undefined') {
  (window as any).resetMyTokens = resetMyTokens;
  (globalThis as any).resetMyTokens = resetMyTokens;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('💡 Console helper loaded! Type: await resetMyTokens()');
  }
}
