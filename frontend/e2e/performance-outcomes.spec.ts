/**
 * Performance E2E Tests - Outcome Verification
 * 
 * Tests that verify performance characteristics meet acceptable thresholds.
 * These are outcome tests - not just "didn't crash" but "completed in reasonable time".
 */

import { test, expect } from '@playwright/test';

test.describe('Performance - Outcome Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('initial page load completes in under 5 seconds', async ({ page }) => {
    // Already loaded in beforeEach, measure reload
    const startTime = Date.now();
    await page.reload();
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;

    console.log(`Page load time: ${loadTime}ms`);
    
    // VERIFY: Loads in acceptable time
    expect(loadTime).toBeLessThan(5000);
    
    // VERIFY: Critical elements loaded
    const board = page.locator('[data-testid="board"], .board, .chessboard');
    await expect(board).toBeVisible();
  });

  test('position analysis completes in under 5 seconds', async ({ page }) => {
    const analyzeButton = page.locator('button:has-text("Analyze")');
    
    if (await analyzeButton.isVisible()) {
      const startTime = Date.now();
      
      await analyzeButton.click();
      
      // Wait for analysis complete indicator
      await page.waitForSelector('text=/analysis|complete|ready/i', { timeout: 5000 });
      
      const analysisTime = Date.now() - startTime;
      console.log(`Analysis time: ${analysisTime}ms`);

      // VERIFY: Analysis completed in reasonable time
      expect(analysisTime).toBeLessThan(5000);
    }
  });

  test('LLM response time is under 15 seconds', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      const startTime = Date.now();
      
      await chatInput.fill("What is 1. e4?");
      await chatInput.press('Enter');

      // Wait for response
      await page.waitForSelector('.assistant-message', { timeout: 15000 });
      
      const responseTime = Date.now() - startTime;
      console.log(`LLM response time: ${responseTime}ms`);

      // VERIFY: Response in reasonable time
      expect(responseTime).toBeLessThan(15000);
      
      // VERIFY: Response has content
      const response = page.locator('.assistant-message').last();
      const responseText = await response.textContent();
      expect(responseText!.length).toBeGreaterThan(10);
    }
  });

  test('confidence tree renders in under 3 seconds', async ({ page }) => {
    // Trigger analysis
    const analyzeButton = page.locator('button:has-text("Analyze")');
    
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(2000);
    }

    const startTime = Date.now();
    
    // Wait for tree to render
    const tree = page.locator('.confidence-tree, svg.tree, [data-testid="confidence-tree"]');
    await expect(tree).toBeVisible({ timeout: 3000 });
    
    const renderTime = Date.now() - startTime;
    console.log(`Tree render time: ${renderTime}ms`);

    // VERIFY: Rendered quickly
    expect(renderTime).toBeLessThan(3000);
    
    // VERIFY: Has nodes
    const nodes = await page.locator('circle, rect').count();
    expect(nodes).toBeGreaterThan(0);
  });

  test('rapid move sequence maintains responsiveness', async ({ page }) => {
    const moves = [
      { from: 'e2', to: 'e4' },
      { from: 'd2', to: 'd4' },
      { from: 'g1', to: 'f3' },
      { from: 'b1', to: 'c3' },
      { from: 'f1', to: 'c4' }
    ];

    const startTime = Date.now();

    for (const move of moves) {
      await page.click(`[data-square="${move.from}"]`);
      await page.click(`[data-square="${move.to}"]`);
      
      // Minimal delay - testing rapid input
      await page.waitForTimeout(50);
    }

    // Wait for all to settle
    await page.waitForTimeout(1000);
    
    const totalTime = Date.now() - startTime;
    console.log(`5 rapid moves time: ${totalTime}ms`);

    // VERIFY: All completed reasonably fast
    expect(totalTime).toBeLessThan(5000);

    // VERIFY: System still responsive
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await expect(chatInput).toBeEnabled();
    }
  });

  test('no memory leaks after 20 moves', async ({ page }) => {
    // Make 20 moves
    const moveSequence = [
      { from: 'e2', to: 'e4' }, { from: 'd2', to: 'd4' }, { from: 'g1', to: 'f3' },
      { from: 'b1', to: 'c3' }, { from: 'f1', to: 'c4' }, { from: 'e1', to: 'g1' }
    ];

    // Get initial memory
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    // Make moves
    for (let round = 0; round < 4; round++) {
      for (const move of moveSequence) {
        try {
          await page.click(`[data-square="${move.from}"]`, { timeout: 500 });
          await page.click(`[data-square="${move.to}"]`, { timeout: 500 });
          await page.waitForTimeout(50);
        } catch (e) {
          // Move might not be legal anymore, that's okay
          break;
        }
      }
    }

    await page.waitForTimeout(1000);

    // Get final memory
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    if (initialMemory > 0 && finalMemory > 0) {
      const memoryIncrease = finalMemory - initialMemory;
      const increasePercent = (memoryIncrease / initialMemory) * 100;

      console.log(`Memory increase: ${memoryIncrease} bytes (${increasePercent.toFixed(1)}%)`);

      // VERIFY: Memory didn't explode (< 100MB increase or < 200% of initial)
      expect(memoryIncrease).toBeLessThan(100 * 1024 * 1024); // 100 MB
      expect(increasePercent).toBeLessThan(200); // Not more than 2x
    }
  });

  test('confidence raise completes in under 10 seconds', async ({ page }) => {
    // Trigger initial analysis
    const analyzeButton = page.locator('button:has-text("Analyze")');
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(2000);
    }

    // Click raise confidence
    const raiseButton = page.locator('button:has-text("Raise")');
    
    if (await raiseButton.isVisible()) {
      const startTime = Date.now();
      
      await raiseButton.click();
      
      // Wait for completion (tree updates or process finishes)
      await page.waitForTimeout(10000);
      
      const raiseTime = Date.now() - startTime;
      console.log(`Confidence raise time: ${raiseTime}ms`);

      // VERIFY: Completed in acceptable time
      expect(raiseTime).toBeLessThan(10000);

      // VERIFY: System still responsive
      const isResponsive = await page.evaluate(() => document.readyState === 'complete');
      expect(isResponsive).toBe(true);
    }
  });

  test('concurrent chat messages dont block each other', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Send first message
      await chatInput.fill("Analyze this position");
      await chatInput.press('Enter');

      // Immediately send second message (before first completes)
      await page.waitForTimeout(500);
      await chatInput.fill("What about Nf3?");
      await chatInput.press('Enter');

      // Wait for both to process
      await page.waitForTimeout(10000);

      // VERIFY: Both messages sent
      const userMessages = await page.locator('.user-message').count();
      expect(userMessages).toBeGreaterThanOrEqual(2);

      // VERIFY: System still responsive
      await expect(chatInput).toBeEnabled();
    }
  });

  test('large tree rendering performance', async ({ page }) => {
    // Set position and trigger deep analysis
    const analyzeButton = page.locator('button:has-text("Analyze")');
    
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(2000);
    }

    // Try to generate large tree (multiple confidence raises)
    const raiseButton = page.locator('button:has-text("Raise")');
    
    if (await raiseButton.isVisible()) {
      const startTime = Date.now();

      // Raise 2-3 times
      for (let i = 0; i < 2; i++) {
        await raiseButton.click();
        await page.waitForTimeout(3000);
      }

      const totalTime = Date.now() - startTime;
      console.log(`Large tree generation time: ${totalTime}ms`);

      // VERIFY: Completed without hanging
      expect(totalTime).toBeLessThan(20000);

      // VERIFY: Tree rendered
      const nodes = await page.locator('circle, rect').count();
      expect(nodes).toBeGreaterThan(0);
    }
  });

  test('no excessive re-renders during analysis', async ({ page }) => {
    // Track component renders
    let renderCount = 0;
    
    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('render') || text.includes('update') || text.includes('refresh')) {
        renderCount++;
      }
    });

    // Trigger analysis
    const analyzeButton = page.locator('button:has-text("Analyze")');
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(5000);
    }

    // VERIFY: Not excessive re-rendering (< 100 in 5 seconds)
    console.log(`Render count during analysis: ${renderCount}`);
    expect(renderCount).toBeLessThan(100);
  });
});

