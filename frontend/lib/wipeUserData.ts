/**
 * Console helper to wipe user data for testing
 * 
 * Usage in browser console:
 *   await wipeMyData()
 * 
 * Or if you have the user ID:
 *   await wipeMyData('a1652893-3bd8-46b2-a5aa-c28609c84f01')
 */

import { getBackendBase } from './backendBase';
import { supabase } from './supabase';

export async function wipeMyData(userId?: string): Promise<void> {
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

    console.log(`🗑️  Wiping data for user: ${userId}...`);
    
    const backendBase = getBackendBase();
    const response = await fetch(`${backendBase}/profile/wipe-my-data`, {
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
    console.log('✅ Wipe complete!', result);
    console.log(`   Deleted:`, result.deleted);
    console.log(`   ${result.message}`);
    
  } catch (error) {
    console.error('❌ Error wiping data:', error);
  }
}

// Make it available on window for easy console access
if (typeof window !== 'undefined') {
  (window as any).wipeMyData = wipeMyData;
  console.log('💡 Console helper loaded! Type: await wipeMyData()');
}
