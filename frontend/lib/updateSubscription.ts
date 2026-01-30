/**
 * Console helper to update subscription tier for testing
 * 
 * Usage in browser console:
 *   await updateMySubscription('lite')
 *   await updateMySubscription('starter')
 *   await updateMySubscription('full')
 *   await updateMySubscription('unpaid')
 * 
 * Or if you have the user ID:
 *   await updateMySubscription('lite', 'a1652893-3bd8-46b2-a5aa-c28609c84f01')
 */

"use client";

import { getBackendBase } from './backendBase';
import { supabase } from './supabase';

export async function updateMySubscription(tierId: string, userId?: string): Promise<void> {
  try {
    // Validate tier_id
    const validTiers = ['unpaid', 'lite', 'starter', 'full'];
    const normalizedTierId = tierId.toLowerCase();
    
    if (!validTiers.includes(normalizedTierId)) {
      console.error(`❌ Invalid tier_id: ${tierId}. Must be one of: ${validTiers.join(', ')}`);
      return;
    }

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

    console.log(`🔄 Updating subscription to tier: ${normalizedTierId} for user: ${userId}...`);
    
    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/admin/update-subscription`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        user_id: userId,
        tier_id: normalizedTierId
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error(`❌ Error: ${response.status} - ${error}`);
      return;
    }

    const result = await response.json();
    console.log('✅ Subscription updated!', result);
    console.log(`   ${result.message || `Subscription updated to ${normalizedTierId}`}`);
    console.log(`   💡 You may need to refresh the page to see the changes.`);
    
  } catch (error) {
    console.error('❌ Error updating subscription:', error);
  }
}

// Make it available on window for easy console access
if (typeof window !== 'undefined') {
  (window as any).updateMySubscription = updateMySubscription;
  (globalThis as any).updateMySubscription = updateMySubscription;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('💡 Console helper loaded! Type: await updateMySubscription("lite")');
  }
}
