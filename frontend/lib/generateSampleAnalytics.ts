/**
 * Console helper to generate sample analytics data for testing
 * 
 * Usage in browser console:
 *   await generateSampleAnalytics()
 * 
 * Or with options:
 *   await generateSampleAnalytics({ gamesCount: 60, overwrite: true })
 * 
 * This will:
 * 1. Auto-detect the logged-in user
 * 2. Generate realistic sample analytics data
 * 3. Populate the detailed_analytics_cache so the dashboard loads instantly
 */

"use client";

import { getBackendBase } from './backendBase';
import { supabase } from './supabase';

interface GenerateSampleAnalyticsOptions {
  gamesCount?: number;
  overwrite?: boolean;
}

export async function generateSampleAnalytics(options: GenerateSampleAnalyticsOptions = {}): Promise<void> {
  try {
    // Auto-detect logged-in user
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      console.error('❌ Not logged in. Please log in first.');
      return;
    }
    
    const userId = user.id;
    console.log(`✅ Detected logged-in user: ${userId}`);
    
    const gamesCount = options.gamesCount || 40;
    const overwrite = options.overwrite || false;
    
    console.log(`🎲 Generating sample analytics data...`);
    console.log(`   Games count: ${gamesCount}`);
    console.log(`   Overwrite existing: ${overwrite ? 'Yes' : 'No'}`);
    
    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/admin/generate-sample-analytics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        games_count: gamesCount,
        overwrite: overwrite
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error(`❌ Error: ${response.status} - ${error}`);
      return;
    }

    const result = await response.json();
    
    if (result.status === 'skipped') {
      console.warn(`⚠️  ${result.message}`);
      console.log(`   Use: await generateSampleAnalytics({ overwrite: true }) to replace existing cache`);
      return;
    }
    
    if (result.status === 'success') {
      console.log('✅ Sample analytics generated successfully!');
      console.log(`   ${result.message}`);
      console.log(`\n📊 Generated data includes:`);
      const summary = result.data_summary || {};
      console.log(`   - Phases: ${summary.phases || 0}`);
      console.log(`   - Openings: ${summary.openings || 0}`);
      console.log(`   - Pieces: ${summary.pieces || 0}`);
      console.log(`   - Tags gained: ${summary.tags_gained || 0}`);
      console.log(`   - Tags lost: ${summary.tags_lost || 0}`);
      console.log(`   - Static tags: ${summary.static_tags || 0}`);
      console.log(`   - Time buckets: ${summary.time_buckets || 0}`);
      console.log(`\n💡 Refresh the Profile Dashboard → Habits & Patterns tab to see the data!`);
    } else {
      console.error(`❌ Failed: ${result.message || 'Unknown error'}`);
    }
    
  } catch (error) {
    console.error('❌ Error generating sample analytics:', error);
  }
}

// Make it available on window for easy console access
if (typeof window !== 'undefined') {
  (window as any).generateSampleAnalytics = generateSampleAnalytics;
  (globalThis as any).generateSampleAnalytics = generateSampleAnalytics;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('💡 Console helper loaded! Type: await generateSampleAnalytics()');
  }
}
