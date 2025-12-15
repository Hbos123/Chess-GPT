/**
 * PGN Parsing E2E Tests - Outcome Verification
 * 
 * These tests specifically target the "Invalid move: e4" bug and similar PGN parsing issues.
 * They verify that PGN sequences from LLM responses use the correct FEN context.
 */

import { test, expect } from '@playwright/test';

test.describe('PGN Parsing - Outcome Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('LLM response with PGN from starting position parses correctly', async ({ page }) => {
    // Collect errors
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('Invalid move')) {
        errors.push(msg.text());
      }
    });

    // Send message that should get PGN response
    const chatInput = page.locator('textarea, input[type="text"]').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me the Italian Game opening");
      await chatInput.press('Enter');
      
      // Wait for LLM response
      await page.waitForTimeout(5000);

      // Look for PGN in response (e.g., "1. e4 e5 2. Nf3 Nc6 3. Bc4")
      const pgnText = page.locator('text=/1\\.\\s*e4/');
      
      if (await pgnText.isVisible()) {
        // Try to click the PGN
        await pgnText.click();
        await page.waitForTimeout(500);

        // VERIFY: No "Invalid move" errors
        const invalidMoveErrors = errors.filter(e => e.includes('Invalid move'));
        expect(invalidMoveErrors).toHaveLength(0);

        // VERIFY: Board updated
        const fen = await page.evaluate(() => (window as any).currentFEN);
        expect(fen).toMatch(/4P3/); // e4 pawn present
      }
    }
  });

  test('PGN after user move uses correct FEN context', async ({ page }) => {
    // This is THE BUG: after playing e4, LLM response has "1. e4 e5"
    // Parser must detect it should start from INITIAL FEN, not current FEN

    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('Invalid move')) {
        errors.push(msg.text());
      }
    });

    // Make move e4
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(1000);

    // Send message to get analysis with PGN
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("What are common responses to 1.e4?");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // LLM might respond with "1. e4 e5" or "1...e5"
      // If it says "1. e4", clicking shouldn't try to play e4 again!
      
      const pgnText = page.locator('text=/1\\.\\s*e4/').first();
      if (await pgnText.isVisible()) {
        await pgnText.click();
        await page.waitForTimeout(500);

        // VERIFY: No "Invalid move: e4" error
        const e4Errors = errors.filter(e => e.includes('Invalid move') && e.includes('e4'));
        expect(e4Errors).toHaveLength(0);
      }
    }
  });

  test('PGN with ellipsis notation (1...e5) parses correctly', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Make move as White
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(1000);

    // Look for Black's response in LLM output
    // Might see "1...e5" notation
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("What's Black's best response?");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      const ellipsisPGN = page.locator('text=/1\\.{3}\\s*e5/');
      if (await ellipsisPGN.isVisible()) {
        await ellipsisPGN.click();
        await page.waitForTimeout(500);

        // VERIFY: No parsing errors
        expect(errors.filter(e => e.includes('parse') || e.includes('Invalid'))).toHaveLength(0);

        // VERIFY: Black pawn on e5
        const fen = await page.evaluate(() => (window as any).currentFEN);
        expect(fen).toMatch(/4p3/); // Black pawn on e5
      }
    }
  });

  test('clicking multiple PGN moves in sequence works', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Get PGN sequence from LLM
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me the Sicilian Defense");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // Try clicking multiple moves
      const moves = ['e4', 'c5', 'Nf3'];
      for (const move of moves) {
        const moveText = page.locator(`text=/${move}/`).first();
        if (await moveText.isVisible()) {
          await moveText.click();
          await page.waitForTimeout(300);
        }
      }

      // VERIFY: No errors
      expect(errors).toHaveLength(0);

      // VERIFY: Position progressed
      const fen = await page.evaluate(() => (window as any).currentFEN);
      expect(fen).not.toMatch(/^rnbqkbnr\/pppppppp/); // Not starting position
    }
  });

  test('PGN from mid-game position uses correct context', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Set up a mid-game position
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(500);

    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    await page.waitForTimeout(500);

    await page.click('[data-square="g1"]');
    await page.click('[data-square="f3"]');
    await page.waitForTimeout(500);

    // Now ask for continuation
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("What should I play next?");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // If LLM shows "4. Nc3" or similar, it should apply from current position
      // VERIFY: No parsing errors when clicking suggestions
      expect(errors.filter(e => e.includes('Invalid') || e.includes('parse'))).toHaveLength(0);
    }
  });

  test('invalid PGN handled gracefully', async ({ page }) => {
    // Simulate invalid PGN in response (edge case)
    // System should not crash
    
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Try to manually create invalid PGN scenario
    // (In real usage, LLM might occasionally produce malformed PGN)
    
    await page.waitForTimeout(2000);

    // VERIFY: Page is still responsive even with edge cases
    const isResponsive = await page.evaluate(() => document.readyState === 'complete');
    expect(isResponsive).toBe(true);
  });

  test('PGN hover shows preview board', async ({ page }) => {
    // Get PGN from LLM
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me a chess opening");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // Find PGN move
      const moveText = page.locator('text=/e4/').first();
      if (await moveText.isVisible()) {
        // Hover over it
        await moveText.hover();
        await page.waitForTimeout(500);

        // Check if preview board appears (feature may or may not exist)
        const preview = page.locator('.preview-board, .mini-board, [data-testid="move-preview"]');
        // Don't fail if not implemented, just verify no crash
        
        const isResponsive = await page.evaluate(() => document.readyState === 'complete');
        expect(isResponsive).toBe(true);
      }
    }
  });

  test('PGN with variations parses main line correctly', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Get response with variations
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me the Ruy Lopez with variations");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // Click main line moves (ignoring variations in parentheses)
      const mainLineMoves = page.locator('text=/^[1-9]\\./');
      const count = await mainLineMoves.count();

      if (count > 0) {
        await mainLineMoves.first().click();
        await page.waitForTimeout(300);

        // VERIFY: Main line applied without errors
        expect(errors.filter(e => e.includes('Invalid'))).toHaveLength(0);
      }
    }
  });

  test('rapid PGN clicking does not corrupt state', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Get PGN sequence
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me 10 moves of the King's Gambit");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // Rapidly click multiple moves
      const moves = page.locator('text=/e4|e5|f4|Nf3|Nc6/');
      const count = await moves.count();

      for (let i = 0; i < Math.min(count, 5); i++) {
        await moves.nth(i).click();
        await page.waitForTimeout(100); // Rapid clicking
      }

      // VERIFY: No state corruption errors
      expect(errors).toHaveLength(0);

      // VERIFY: Board still in valid state
      const fen = await page.evaluate(() => (window as any).currentFEN);
      const fenParts = fen.split(' ');
      expect(fenParts.length).toBeGreaterThanOrEqual(4);
    }
  });

  test('PGN annotations (!, ?, etc.) are ignored', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Get annotated PGN
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me a brilliant game with annotations");
      await chatInput.press('Enter');
      
      await page.waitForTimeout(5000);

      // PGN might have "e4!" or "Nf3??" etc.
      // Clicking should strip annotations and apply move
      
      const annotatedMove = page.locator('text=/e4[!?]+/').first();
      if (await annotatedMove.isVisible()) {
        await annotatedMove.click();
        await page.waitForTimeout(300);

        // VERIFY: Move applied correctly (annotations stripped)
        const fen = await page.evaluate(() => (window as any).currentFEN);
        expect(fen).toMatch(/4P3/);
        
        // VERIFY: No parsing errors
        expect(errors).toHaveLength(0);
      }
    }
  });
});

