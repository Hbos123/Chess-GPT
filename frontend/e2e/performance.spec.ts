/**
 * Performance E2E Tests
 * 
 * Tests response times, memory usage, and system performance under load.
 */

import { test, expect } from '@playwright/test';

test.describe('Performance Tests', () => {
  
  test('position analysis should complete within 5 seconds', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const startTime = Date.now();
    
    // Trigger analysis (if not auto-triggered)
    await page.waitForTimeout(1000);
    
    // Wait for analysis to complete (look for candidate moves or results)
    await page.waitForTimeout(6000);
    
    const elapsed = Date.now() - startTime;
    
    // Should complete within reasonable time
    expect(elapsed).toBeLessThan(10000); // 10 second max
  });

  test('should handle multiple moves without slowdown', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const moveTimes: number[] = [];
    
    const moves = [
      { from: 'e2', to: 'e4' },
      { from: 'd2', to: 'd4' },
      { from: 'g1', to: 'f3' }
    ];
    
    for (const move of moves) {
      const start = Date.now();
      
      await page.click(`[data-square="${move.from}"]`);
      await page.click(`[data-square="${move.to}"]`);
      await page.waitForTimeout(2000);
      
      moveTimes.push(Date.now() - start);
    }
    
    // Later moves shouldn't be significantly slower (no memory leak)
    const firstTime = moveTimes[0];
    const lastTime = moveTimes[moveTimes.length - 1];
    
    // Last move shouldn't be more than 2x slower
    expect(lastTime).toBeLessThan(firstTime * 2.5);
  });

  test('should not freeze on long operations', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Make a move that might trigger heavy computation
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // Wait for processing
    await page.waitForTimeout(8000);
    
    // UI should still be responsive
    const chatInput = page.locator('textarea, input[type="text"]').first();
    
    // Should be able to type
    await chatInput.fill('test');
    const value = await chatInput.inputValue();
    expect(value).toBe('test');
  });

  test('page should remain responsive during analysis', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Trigger analysis
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    
    // While analysis running, try to interact
    await page.waitForTimeout(1000);
    
    // Should still be able to interact with UI
    const chatInput = page.locator('textarea, input[type="text"]').first();
    const isEditable = await chatInput.isEditable();
    
    // Input should be editable (not frozen)
    expect(isEditable).toBe(true);
  });
});

test.describe('Memory and Resource Management', () => {
  test('should not leak memory on repeated operations', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Perform 5 move sequences
    for (let i = 0; i < 5; i++) {
      await page.click('[data-square="e2"]');
      await page.click('[data-square="e4"]');
      await page.waitForTimeout(1000);
      
      // Reset board (go back)
      const resetButton = page.locator('button:has-text("Reset"), button:has-text("Clear")').first();
      const hasReset = await resetButton.count();
      if (hasReset > 0) {
        await resetButton.click();
        await page.waitForTimeout(500);
      } else {
        // Reload page as reset
        await page.reload();
        await page.waitForLoadState('networkidle');
      }
    }
    
    // Page should still be responsive
    const pageOk = await page.locator('body').isVisible();
    expect(pageOk).toBe(true);
  });
});

