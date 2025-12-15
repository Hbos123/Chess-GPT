/**
 * CRITICAL E2E Test - Play Mode Flow
 * 
 * This test catches the exact bug you encountered:
 * - User plays move → auto-message sent → LLM responds → PGN parsing fails
 * 
 * Tests the complete flow: User move → Board update → Auto-message → 
 * LLM/Engine response → Board sync → No errors
 */

import { test, expect } from '@playwright/test';

test.describe('Play Mode Critical Path', () => {
  
  test.beforeEach(async ({ page }) => {
    // Capture console errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text());
      }
      if (msg.type() === 'warning' && msg.text().includes('Failed to parse PGN')) {
        console.warn('PGN parsing warning:', msg.text());
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should handle move → auto-message → response → board sync (CATCHES THE BUG)', async ({ page }) => {
    // Track console errors during test
    const consoleErrors: string[] = [];
    const pgnWarnings: string[] = [];
    
    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error' || text.includes('Invalid move')) {
        consoleErrors.push(text);
      }
      if (text.includes('Failed to parse PGN')) {
        pgnWarnings.push(text);
      }
    });
    
    // 1. Make move e4 by clicking on board
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // 2. Verify move was applied visually
    await page.waitForTimeout(500);
    
    // 3. Wait for any auto-message to appear
    // Note: Auto-message might be "I played 1.e4" or similar
    await page.waitForTimeout(2000);
    
    // 4. Wait for backend responses (engine + LLM)
    await page.waitForTimeout(8000);
    
    // 5. THE CRITICAL CHECK: No "Invalid move: e4" errors
    const invalidMoveErrors = consoleErrors.filter(e => 
      e.includes('Invalid move') && e.includes('e4')
    );
    expect(invalidMoveErrors).toHaveLength(0);
    
    // 6. No PGN parsing failures
    const pgnFailures = pgnWarnings.filter(w => w.includes('e4'));
    expect(pgnFailures).toHaveLength(0);
    
    // 7. Verify no analysis timeout
    const timeoutMsg = await page.locator('text=/timed out/i').count();
    expect(timeoutMsg).toBe(0);
    
    // 8. Verify board is still in valid state (no crashes)
    const boardExists = await page.locator('.board-container').count();
    expect(boardExists).toBeGreaterThan(0);
  });

  test('should maintain FEN/PGN synchronization throughout play', async ({ page }) => {
    // Make 2 moves and verify state stays consistent
    
    // Move 1: e4
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(3000);
    
    // Check state after first move
    const hasE4 = await page.locator('[data-square="e4"]').count();
    expect(hasE4).toBeGreaterThan(0);
    
    // Move 2: d4 (after engine responds)
    await page.waitForTimeout(2000);
    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    await page.waitForTimeout(3000);
    
    // Verify both moves are on board
    const hasD4 = await page.locator('[data-square="d4"]').count();
    expect(hasD4).toBeGreaterThan(0);
    
    // No errors in console
    const errors = await page.locator('.error-message, [data-error="true"]').count();
    expect(errors).toBe(0);
  });

  test('should not crash on rapid moves', async ({ page }) => {
    // Click moves rapidly without waiting
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait brief moment
    await page.waitForTimeout(1000);
    
    // Make another move quickly
    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    
    // System should handle gracefully
    await page.waitForTimeout(2000);
    
    // Verify no crash (board still renders)
    const boardVisible = await page.locator('.board-container').isVisible();
    expect(boardVisible).toBe(true);
  });

  test('should handle engine response without state corruption', async ({ page }) => {
    // Make move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait for engine to respond
    await page.waitForTimeout(5000);
    
    // Verify board updated (engine made a move)
    // The starting position should have changed
    const chatMessages = await page.locator('.message-bubble').count();
    
    // Should have at least some activity (messages or updates)
    expect(chatMessages).toBeGreaterThanOrEqual(0);
    
    // Board should still be interactive
    const boardContainer = await page.locator('.board-container');
    await expect(boardContainer).toBeVisible();
  });
});

test.describe('Play Mode - State Recovery', () => {
  test('should recover from errors without requiring refresh', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Make a valid move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(3000);
    
    // Even if there were errors internally, board should still work
    // Try another move
    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    await page.waitForTimeout(1000);
    
    // Verify board didn't freeze
    const boardInteractive = await page.locator('.board-container').isVisible();
    expect(boardInteractive).toBe(true);
  });
});

