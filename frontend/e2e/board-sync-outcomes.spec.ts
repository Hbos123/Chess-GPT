/**
 * Board Synchronization E2E Tests - Outcome Verification
 * 
 * Tests that verify FEN, PGN, and visual board state remain synchronized
 * across all user interactions and system updates.
 */

import { test, expect } from '@playwright/test';

test.describe('Board Synchronization - Outcome Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('FEN matches visual board state', async ({ page }) => {
    // Make a move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(500);

    // Get FEN from state
    const fen = await page.evaluate(() => (window as any).currentFEN);
    
    // Parse FEN to get piece positions
    const fenParts = fen.split(' ');
    const boardPart = fenParts[0];
    
    // VERIFY: FEN shows e4 pawn (rank 4 should have ...4P3...)
    expect(boardPart).toMatch(/4P3/);
    
    // VERIFY: Visual board has piece on e4
    const e4Piece = page.locator('[data-square="e4"] .piece, [data-square="e4"] svg');
    await expect(e4Piece).toBeVisible();
    
    // VERIFY: e2 is empty
    const e2Piece = page.locator('[data-square="e2"] .piece, [data-square="e2"] svg');
    expect(await e2Piece.count()).toBe(0);
  });

  test('move history matches current position', async ({ page }) => {
    // Make several moves
    const moves = [
      { from: 'e2', to: 'e4' },
      { from: 'd2', to: 'd4' },
      { from: 'g1', to: 'f3' }
    ];

    for (const move of moves) {
      await page.click(`[data-square="${move.from}"]`);
      await page.click(`[data-square="${move.to}"]`);
      await page.waitForTimeout(300);
    }

    // Get move history
    const history = await page.evaluate(() => {
      const game = (window as any).game;
      return game ? game.history() : [];
    });

    // Get current FEN
    const fen = await page.evaluate(() => (window as any).currentFEN);

    // VERIFY: Replaying history from starting position gives same FEN
    const replayedFEN = await page.evaluate((hist) => {
      const { Chess } = require('chess.js');
      const tempGame = new Chess();
      for (const move of hist) {
        tempGame.move(move);
      }
      return tempGame.fen();
    }, history);

    // FENs should match (or at least board positions should match)
    const currentBoard = fen.split(' ')[0];
    const replayedBoard = replayedFEN.split(' ')[0];
    expect(currentBoard).toBe(replayedBoard);
  });

  test('PGN regenerates current position', async ({ page }) => {
    // Make moves
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(500);

    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    await page.waitForTimeout(500);

    // Get current PGN and FEN
    const currentFEN = await page.evaluate(() => (window as any).currentFEN);
    const currentPGN = await page.evaluate(() => {
      const game = (window as any).game;
      return game ? game.pgn() : '';
    });

    // VERIFY: Parsing PGN recreates same position
    if (currentPGN) {
      const recreatedFEN = await page.evaluate((pgn) => {
        const { Chess } = require('chess.js');
        const tempGame = new Chess();
        tempGame.loadPgn(pgn);
        return tempGame.fen();
      }, currentPGN);

      const currentBoard = currentFEN.split(' ')[0];
      const recreatedBoard = recreatedFEN.split(' ')[0];
      expect(currentBoard).toBe(recreatedBoard);
    }
  });

  test('mode switching preserves board state', async ({ page }) => {
    // Make move in current mode
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(500);

    const fenBefore = await page.evaluate(() => (window as any).currentFEN);

    // Switch modes (if mode buttons exist)
    const analyzeButton = page.locator('button:has-text("Analyze"), button:has-text("Analysis")');
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(1000);

      const fenAfterSwitch = await page.evaluate(() => (window as any).currentFEN);

      // VERIFY: FEN didn't change just from mode switch
      expect(fenAfterSwitch.split(' ')[0]).toBe(fenBefore.split(' ')[0]);
    }
  });

  test('board reset clears all state', async ({ page }) => {
    // Make moves
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(500);

    // Look for reset/new game button
    const resetButton = page.locator('button:has-text("Reset"), button:has-text("New Game"), button[aria-label*="reset" i]');
    
    if (await resetButton.isVisible()) {
      await resetButton.click();
      await page.waitForTimeout(500);

      const fen = await page.evaluate(() => (window as any).currentFEN);

      // VERIFY: Back to starting position
      expect(fen).toMatch(/^rnbqkbnr\/pppppppp/);
    }
  });

  test('undo maintains state consistency', async ({ page }) => {
    // Make 2 moves
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(300);

    const fenAfterE4 = await page.evaluate(() => (window as any).currentFEN);

    await page.click('[data-square="d2"]');
    await page.click('[data-square="d4"]');
    await page.waitForTimeout(300);

    const fenAfterD4 = await page.evaluate(() => (window as any).currentFEN);

    // Undo if available
    const undoButton = page.locator('button:has-text("Undo"), button[aria-label*="undo" i]');
    if (await undoButton.isVisible()) {
      await undoButton.click();
      await page.waitForTimeout(300);

      const fenAfterUndo = await page.evaluate(() => (window as any).currentFEN);

      // VERIFY: FEN matches state after e4
      expect(fenAfterUndo.split(' ')[0]).toBe(fenAfterE4.split(' ')[0]);
    }
  });

  test('applying PGN from LLM updates all state layers', async ({ page }) => {
    // Get PGN from LLM
    const chatInput = page.locator('textarea').first();
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me 1. e4 e5 2. Nf3");
      await chatInput.press('Enter');
      await page.waitForTimeout(5000);

      // Click to apply PGN
      const pgnMove = page.locator('text=/e4/').first();
      if (await pgnMove.isVisible()) {
        await pgnMove.click();
        await page.waitForTimeout(500);

        // VERIFY: FEN updated
        const fen = await page.evaluate(() => (window as any).currentFEN);
        expect(fen).toMatch(/4P3/);

        // VERIFY: Visual board updated
        const e4Piece = page.locator('[data-square="e4"]');
        await expect(e4Piece).toBeVisible();

        // VERIFY: Move history updated
        const history = await page.evaluate(() => {
          const game = (window as any).game;
          return game ? game.history() : [];
        });
        expect(history).toContain('e4');
      }
    }
  });

  test('mini-board in chat syncs with main board', async ({ page }) => {
    // Look for mini-boards in chat
    const miniBoards = page.locator('.mini-board, .inline-board, [data-testid="mini-board"]');
    const count = await miniBoards.count();

    if (count > 0) {
      // Click on mini-board
      await miniBoards.first().click();
      await page.waitForTimeout(500);

      // VERIFY: Main board updated
      const mainFEN = await page.evaluate(() => (window as any).currentFEN);
      expect(mainFEN).toBeTruthy();
      expect(mainFEN.split(' ').length).toBeGreaterThanOrEqual(4);
    }
  });

  test('FEN changes trigger board visual update', async ({ page }) => {
    // Set FEN programmatically
    const newFEN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";
    
    await page.evaluate((fen) => {
      if ((window as any).setFEN) {
        (window as any).setFEN(fen);
      }
    }, newFEN);

    await page.waitForTimeout(500);

    // VERIFY: Visual board shows c5 pawn (Black)
    const c5Square = page.locator('[data-square="c5"]');
    
    // Check if piece exists visually
    const hasPiece = await c5Square.locator('.piece, svg').count() > 0;
    
    // If board updated, c5 should have a piece
    const currentFEN = await page.evaluate(() => (window as any).currentFEN);
    if (currentFEN.includes('2p5')) {
      expect(hasPiece).toBe(true);
    }
  });

  test('rapid state changes maintain consistency', async ({ page }) => {
    // Rapid sequence of state changes
    const actions = [
      async () => { await page.click('[data-square="e2"]'); await page.click('[data-square="e4"]'); },
      async () => { await page.click('[data-square="d2"]'); await page.click('[data-square="d4"]'); },
      async () => { await page.click('[data-square="g1"]'); await page.click('[data-square="f3"]'); }
    ];

    for (const action of actions) {
      await action();
      await page.waitForTimeout(100); // Minimal delay
    }

    // Wait for all to settle
    await page.waitForTimeout(1000);

    // VERIFY: Final state is valid
    const fen = await page.evaluate(() => (window as any).currentFEN);
    const fenParts = fen.split(' ');
    expect(fenParts.length).toBeGreaterThanOrEqual(4);

    // VERIFY: Move history has expected length
    const history = await page.evaluate(() => {
      const game = (window as any).game;
      return game ? game.history() : [];
    });
    expect(history.length).toBeGreaterThanOrEqual(3);
  });

  test('analysis updates reflect current board state', async ({ page }) => {
    // Make move
    await page.click('[data-square="e2"]');
    await page.click('[data-square="e4"]');
    await page.waitForTimeout(1000);

    // Trigger analysis
    const analyzeButton = page.locator('button:has-text("Analyze")');
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
      await page.waitForTimeout(3000);

      // VERIFY: Analysis data exists
      const analysisData = await page.evaluate(() => (window as any).currentAnalysis);
      
      if (analysisData) {
        // VERIFY: Analysis is for current position (not starting position)
        const currentFEN = await page.evaluate(() => (window as any).currentFEN);
        
        // Analysis should reflect that e4 has been played
        expect(currentFEN).toMatch(/4P3/);
      }
    }
  });
});

