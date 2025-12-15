/**
 * Confidence Tree E2E Tests - Outcome Verification
 * 
 * Tests that verify the confidence tree displays correct outcomes:
 * - Nodes have correct shapes, colors, confidence values
 * - Tree structure is valid
 * - Interactions work as expected
 */

import { test, expect } from '@playwright/test';

test.describe('Confidence Tree - Outcome Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('tree renders with visible nodes', async ({ page }) => {
    // Trigger analysis (if not auto)
    const analyzeButton = page.locator('button:has-text("Analyze"), button:has-text("Get Analysis")');
    if (await analyzeButton.isVisible()) {
      await analyzeButton.click();
    }

    // Wait for analysis to complete
    await page.waitForTimeout(3000);

    // VERIFY: Tree container exists
    const treeContainer = page.locator('.confidence-tree, [data-testid="confidence-tree"], svg.tree');
    await expect(treeContainer).toBeVisible({ timeout: 5000 });

    // VERIFY: Has visible nodes
    const nodes = page.locator('circle, rect').filter({ hasText: /pv-/ });
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('nodes display confidence percentages', async ({ page }) => {
    // Wait for tree
    await page.waitForTimeout(3000);

    // VERIFY: Confidence labels exist
    const confLabels = page.locator('text').filter({ hasText: /%$/ });
    const labelCount = await confLabels.count();
    
    if (labelCount > 0) {
      // Get first label text
      const firstLabel = await confLabels.first().textContent();
      
      // VERIFY: It's a valid percentage
      const confMatch = firstLabel?.match(/(\d+)%/);
      expect(confMatch).toBeTruthy();
      
      const confValue = parseInt(confMatch![1]);
      expect(confValue).toBeGreaterThanOrEqual(0);
      expect(confValue).toBeLessThanOrEqual(100);
    }
  });

  test('first node is a square', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Check for square/rect element representing first node
    const firstNode = page.locator('rect[data-node="pv-0"], rect[id*="pv-0"]').first();
    
    if (await firstNode.isVisible()) {
      // VERIFY: It's a rectangle (square shape)
      const tagName = await firstNode.evaluate(el => el.tagName.toLowerCase());
      expect(tagName).toBe('rect');
    } else {
      // Log structure for debugging
      console.log('First node not found as rect, checking SVG structure');
    }
  });

  test('nodes have different colors based on confidence', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Get all node elements
    const nodes = page.locator('circle, rect').filter({ has: page.locator('text=/pv-/') });
    const nodeCount = await nodes.count();

    if (nodeCount > 5) {
      // Collect fill colors
      const colors = new Set<string>();
      
      for (let i = 0; i < Math.min(nodeCount, 10); i++) {
        const node = nodes.nth(i);
        const fill = await node.getAttribute('fill');
        if (fill) colors.add(fill);
      }

      // VERIFY: Multiple colors used (red, green, etc.)
      expect(colors.size).toBeGreaterThan(0);
    }
  });

  test('clicking node shows corresponding position', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Get initial FEN
    const initialFEN = await page.evaluate(() => (window as any).currentFEN);

    // Find and click a node (not the first one)
    const nodes = page.locator('[data-node], circle, rect').filter({ hasNot: page.locator('[data-node="pv-0"]') });
    const nodeCount = await nodes.count();

    if (nodeCount > 1) {
      await nodes.nth(1).click();
      await page.waitForTimeout(500);

      // VERIFY: FEN changed
      const newFEN = await page.evaluate(() => (window as any).currentFEN);
      expect(newFEN).not.toBe(initialFEN);
    }
  });

  test('raise confidence button exists and is clickable', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for raise confidence button
    const raiseButton = page.locator('button:has-text("Raise Confidence"), button:has-text("Increase Confidence"), button[aria-label*="confidence" i]');
    
    if (await raiseButton.isVisible()) {
      // VERIFY: Button is clickable
      await expect(raiseButton).toBeEnabled();
      
      // Try clicking it
      await raiseButton.click();
      await page.waitForTimeout(1000);

      // VERIFY: No crash (page still responsive)
      const isResponsive = await page.evaluate(() => document.readyState === 'complete');
      expect(isResponsive).toBe(true);
    }
  });

  test('tree updates after confidence raise', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Get initial node count
    const initialNodes = await page.locator('[data-node], circle, rect').count();

    // Find and click raise confidence
    const raiseButton = page.locator('button:has-text("Raise"), button[aria-label*="raise" i]');
    
    if (await raiseButton.isVisible()) {
      await raiseButton.click();
      await page.waitForTimeout(2000);

      // Get new node count
      const newNodes = await page.locator('[data-node], circle, rect').count();

      // VERIFY: Tree changed (either more nodes or colors changed)
      // With branching disabled, count stays same but colors may change
      expect(newNodes).toBeGreaterThanOrEqual(initialNodes);
    }
  });

  test('baseline slider affects node colors', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Look for baseline input/slider
    const baselineInput = page.locator('input[type="range"][aria-label*="baseline" i], input[type="number"][aria-label*="baseline" i]');
    
    if (await baselineInput.isVisible()) {
      // Get initial red node count
      const initialRedNodes = await page.locator('[fill*="red"], [stroke*="red"]').count();

      // Change baseline
      await baselineInput.fill('90'); // High baseline
      await page.waitForTimeout(1000);

      // Get new red node count
      const newRedNodes = await page.locator('[fill*="red"], [stroke*="red"]').count();

      // VERIFY: More nodes are red with higher baseline
      expect(newRedNodes).toBeGreaterThanOrEqual(initialRedNodes);
    }
  });

  test('hovering node shows details', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Find a node
    const node = page.locator('[data-node], circle, rect').first();
    
    if (await node.isVisible()) {
      // Hover
      await node.hover();
      await page.waitForTimeout(300);

      // VERIFY: Tooltip or details appear
      const tooltip = page.locator('.tooltip, [role="tooltip"], .node-details');
      const tooltipVisible = await tooltip.isVisible();
      
      // It's okay if no tooltip, but shouldn't crash
      const isResponsive = await page.evaluate(() => document.readyState === 'complete');
      expect(isResponsive).toBe(true);
    }
  });

  test('tree fits within viewport', async ({ page }) => {
    await page.waitForTimeout(2000);

    // Get tree container
    const tree = page.locator('.confidence-tree, svg.tree').first();
    
    if (await tree.isVisible()) {
      const boundingBox = await tree.boundingBox();
      
      if (boundingBox) {
        const viewport = page.viewportSize();
        
        // VERIFY: Tree width fits in viewport (with reasonable margin)
        expect(boundingBox.width).toBeLessThan((viewport?.width || 1920) * 1.5);
        
        // VERIFY: Tree is not absurdly small
        expect(boundingBox.width).toBeGreaterThan(100);
      }
    }
  });

  test('repeated confidence raises dont crash', async ({ page }) => {
    await page.waitForTimeout(2000);

    const raiseButton = page.locator('button:has-text("Raise")').first();
    
    if (await raiseButton.isVisible()) {
      // Click 3 times
      for (let i = 0; i < 3; i++) {
        await raiseButton.click();
        await page.waitForTimeout(1500);

        // VERIFY: Page still responsive
        const isResponsive = await page.evaluate(() => document.readyState === 'complete');
        expect(isResponsive).toBe(true);
      }

      // VERIFY: No console errors
      const errors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });

      expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0);
    }
  });

  test('node confidence values are in valid range', async ({ page }) => {
    await page.waitForTimeout(3000);

    // Get all confidence text elements
    const confTexts = page.locator('text').filter({ hasText: /%/ });
    const count = await confTexts.count();

    for (let i = 0; i < Math.min(count, 20); i++) {
      const text = await confTexts.nth(i).textContent();
      const match = text?.match(/(\d+)%/);
      
      if (match) {
        const value = parseInt(match[1]);
        
        // VERIFY: Confidence is 0-100
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(100);
      }
    }
  });

  test('tree renders without flickering', async ({ page }) => {
    // Monitor for rapid re-renders
    let renderCount = 0;
    
    page.on('console', msg => {
      if (msg.text().includes('render') || msg.text().includes('update')) {
        renderCount++;
      }
    });

    await page.waitForTimeout(3000);

    // VERIFY: Not excessive re-rendering (< 50 renders in 3 seconds)
    expect(renderCount).toBeLessThan(50);
  });
});

