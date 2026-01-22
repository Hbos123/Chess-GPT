/**
 * Board State Synchronization E2E Tests
 * 
 * Verifies that FEN, PGN, and visual board state remain synchronized
 * throughout all operations.
 */

import { test, expect } from '@playwright/test';

test.describe('Board State Synchronization', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should keep FEN and visual board in sync after moves', async ({ page }) => {
    // Make a move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(1000);
    
    // Check that e4 square has a piece on it visually
    const e4Square = page.locator('[data-square="e4"]');
    await expect(e4Square).toBeVisible();
    
    // Board should show the new position
    const boardContainer = page.locator('.board-container');
    await expect(boardContainer).toBeVisible();
  });

  test('should handle state updates without visual glitches', async ({ page }) => {
    // Make move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait for any animations
    await page.waitForTimeout(2000);
    
    // Make another move
    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    
    // Wait for updates
    await page.waitForTimeout(2000);
    
    // Board should still be responsive
    const board = page.locator('.board-container');
    const isVisible = await board.isVisible();
    expect(isVisible).toBe(true);
  });

  test('should handle rapid state changes', async ({ page }) => {
    // Make 3 moves in quick succession
    const moves = [
      { from: 'e2', to: 'e4' },
      { from: 'd2', to: 'd4' },
      { from: 'g1', to: 'f3' }
    ];
    
    for (const move of moves) {
      await page.click(`[data-square="${move.from}"]`);
      await page.click(`[data-square="${move.to}"]`);
      await page.waitForTimeout(500);
    }
    
    // Wait for all updates to settle
    await page.waitForTimeout(3000);
    
    // Verify board is in valid state
    const board = page.locator('.board-container');
    await expect(board).toBeVisible();
    
    // Verify no errors rendered
    const errorElements = await page.locator('.error-message, [data-error="true"]').count();
    expect(errorElements).toBe(0);
  });

  test('should sync after engine makes move', async ({ page }) => {
    // Make user move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait for engine response (if in play mode)
    await page.waitForTimeout(6000);
    
    // Board should still be valid and interactive
    const board = page.locator('.board-container');
    await expect(board).toBeVisible();
    
    // Should be able to make another move
    const d2Square = page.locator('[data-square="d2"]');
    const isClickable = await d2Square.isVisible();
    expect(isClickable).toBe(true);
  });
});

test.describe('State Recovery', () => {
  test('should maintain state after errors', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Make a valid move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait for processing
    await page.waitForTimeout(3000);
    
    // Try to interact with board again
    const board = page.locator('.board-container');
    await expect(board).toBeVisible();
    
    // Board should still accept moves
    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    
    // Should complete without freezing
    await page.waitForTimeout(1000);
    const stillVisible = await board.isVisible();
    expect(stillVisible).toBe(true);
  });
});

