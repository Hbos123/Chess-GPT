/**
 * Console helper to reset and recalculate detailed analytics
 * 
 * Usage in browser console:
 *   await resetDetailedAnalytics()
 * 
 * Or if you have the user ID:
 *   await resetDetailedAnalytics('a1652893-3bd8-46b2-a5aa-c28609c84f01')
 * 
 * This will:
 * 1. Clear the detailed_analytics_cache for the user
 * 2. Trigger a backfill to recalculate analytics from existing games
 */

"use client";

import { getBackendBase } from './backendBase';
import { supabase } from './supabase';

export async function resetDetailedAnalytics(userId?: string): Promise<void> {
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

    console.log(`🔄 Resetting detailed analytics for user: ${userId}...`);
    
    const backendBase = getBackendBase();
    
    // Step 1: Clear the cache
    console.log('   Step 1: Clearing detailed analytics cache...');
    const clearResponse = await fetch(`${backendBase}/admin/clear-detailed-analytics-cache`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });

    if (!clearResponse.ok) {
      const error = await clearResponse.text();
      console.warn(`⚠️  Warning clearing cache: ${clearResponse.status} - ${error}`);
      // Continue anyway - might not exist
    } else {
      const clearResult = await clearResponse.json();
      console.log('   ✅ Cache cleared:', clearResult);
    }

    // Step 2: Trigger backfill to recalculate
    console.log('   Step 2: Recalculating analytics from games...');
    const backfillResponse = await fetch(`${backendBase}/admin/backfill-detailed-analytics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });

    if (!backfillResponse.ok) {
      const error = await backfillResponse.text();
      console.error(`❌ Error recalculating: ${backfillResponse.status} - ${error}`);
      return;
    }

    const backfillResult = await backfillResponse.json();
    console.log('✅ Detailed analytics reset complete!', backfillResult);
    
    if (backfillResult.results && backfillResult.results.length > 0) {
      const result = backfillResult.results[0];
      if (result.status === 'success') {
        console.log(`   ✅ Recalculated analytics for ${result.games_count || 0} games`);
      } else {
        console.warn(`   ⚠️  Status: ${result.status} - ${result.reason || result.error || 'Unknown'}`);
      }
    }
    
    console.log('   💡 Refresh the profile dashboard to see updated analytics');
    
  } catch (error) {
    console.error('❌ Error resetting detailed analytics:', error);
  }
}

// Make it available on window for easy console access
if (typeof window !== 'undefined') {
  (window as any).resetDetailedAnalytics = resetDetailedAnalytics;
  (globalThis as any).resetDetailedAnalytics = resetDetailedAnalytics;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('💡 Console helper loaded! Type: await resetDetailedAnalytics()');
  }
}
