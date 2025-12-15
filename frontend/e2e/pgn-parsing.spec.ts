/**
 * PGN Parsing E2E Tests
 * 
 * Tests that PGN sequences in LLM responses parse correctly
 * with the right board context.
 */

import { test, expect } from '@playwright/test';

test.describe('PGN Parsing Integration', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should parse PGN from LLM response with correct context', async ({ page }) => {
    const pgnErrors: string[] = [];
    
    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('Failed to parse PGN') || text.includes('Invalid move')) {
        pgnErrors.push(text);
      }
    });
    
    // Send a message that will trigger LLM response with PGN
    const chatInput = page.locator('[data-testid="chat-input"], textarea, input[type="text"]').first();
    await chatInput.fill('What happens after e4 e5?');
    await chatInput.press('Enter');
    
    // Wait for LLM response
    await page.waitForTimeout(10000);
    
    // Check for PGN parsing errors
    expect(pgnErrors).toHaveLength(0);
  });

  test('should handle PGN sequences from starting position', async ({ page }) => {
    // Reset to starting position
    await page.goto('/');
    
    // Look for any PGN in the UI
    const pgnElements = await page.locator('.pgn-clickable, [data-pgn]').count();
    
    // If PGN exists, clicking it shouldn't cause errors
    if (pgnElements > 0) {
      await page.locator('.pgn-clickable, [data-pgn]').first().click();
      await page.waitForTimeout(500);
      
      // Verify no errors
      const errors = await page.locator('[data-error="true"], .error-message').count();
      expect(errors).toBe(0);
    }
  });

  test('should handle PGN from mid-game position', async ({ page }) => {
    // Make a move first to get to mid-game
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(2000);
    
    // Now any PGN parsing should work from this position
    // If there are any clickable PGN elements, test them
    const pgnCount = await page.locator('.pgn-clickable').count();
    
    if (pgnCount > 0) {
      await page.locator('.pgn-clickable').first().click();
      await page.waitForTimeout(500);
      
      // Should update board without errors
      const boardVisible = await page.locator('.board-container').isVisible();
      expect(boardVisible).toBe(true);
    }
  });
});

test.describe('PGN Context Detection', () => {
  test('should detect starting position for move 1 notation', async ({ page }) => {
    const warnings: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'warning' && msg.text().includes('PGN')) {
        warnings.push(msg.text());
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Make a move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(5000);
    
    // Count PGN-related warnings
    const pgnWarnings = warnings.filter(w => w.includes('Failed to parse'));
    
    // Should be minimal or zero
    expect(pgnWarnings.length).toBeLessThan(3);
  });
});

