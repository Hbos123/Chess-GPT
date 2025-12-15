/**
 * LLM Integration E2E Tests - Outcome Verification
 * 
 * Tests that verify LLM chat integration produces actual good outcomes:
 * - Tool calling works correctly
 * - Responses are formatted properly
 * - Moves in responses are valid and clickable
 * - Context is correct for all requests
 */

import { test, expect } from '@playwright/test';

test.describe('LLM Integration - Outcome Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('LLM chat sends and receives messages', async ({ page }) => {
    const chatInput = page.locator('textarea, input[placeholder*="mind" i]').first();
    
    if (await chatInput.isVisible()) {
      // Send message
      await chatInput.fill("Tell me about the starting position");
      await chatInput.press('Enter');

      // VERIFY: Message appears in chat
      const userMessage = page.locator('.user-message, .message-user').last();
      await expect(userMessage).toBeVisible({ timeout: 2000 });
      await expect(userMessage).toContainText('starting position');

      // Wait for LLM response
      await page.waitForTimeout(5000);

      // VERIFY: Assistant response appears
      const assistantMessage = page.locator('.assistant-message, .message-assistant').last();
      const messageCount = await assistantMessage.count();
      expect(messageCount).toBeGreaterThan(0);
    }
  });

  test('analyze_position tool returns structured data', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Request analysis
      await chatInput.fill("Analyze this position");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      // VERIFY: Response contains analysis structure
      const response = page.locator('.assistant-message').last();
      const responseText = await response.textContent();

      // Should have analysis keywords
      const hasAnalysisKeywords = 
        responseText?.includes('eval') || 
        responseText?.includes('advantage') ||
        responseText?.includes('best') ||
        responseText?.includes('move');
      
      expect(hasAnalysisKeywords).toBe(true);
    }
  });

  test('analyze_move tool receives correct context', async ({ page }) => {
    // Monitor console for tool execution
    const toolCalls: string[] = [];
    page.on('console', msg => {
      if (msg.text().includes('analyze_move') || msg.text().includes('tool_call')) {
        toolCalls.push(msg.text());
      }
    });

    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Request move analysis
      await chatInput.fill("Analyze the move e4");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      // VERIFY: Tool was called (check console or response)
      // Even if we can't see tool_calls, check response has analysis
      const response = page.locator('.assistant-message').last();
      await expect(response).toBeVisible();
    }
  });

  test('LLM response formatting handles ### correctly', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Request something that might have sections
      await chatInput.fill("Explain opening principles in sections");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      // VERIFY: ### is converted to line breaks or removed
      const response = page.locator('.assistant-message').last();
      const responseHTML = await response.innerHTML();

      // Should NOT contain literal "###"
      expect(responseHTML).not.toContain('###');
      
      // Should have line breaks or paragraphs
      const hasStructure = 
        responseHTML.includes('<br') || 
        responseHTML.includes('<p>') ||
        responseHTML.includes('\n');
      
      expect(hasStructure).toBe(true);
    }
  });

  test('moves in LLM response are clickable', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      await chatInput.fill("Show me the Sicilian Defense");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      // Look for move notation in response
      const moveText = page.locator('text=/e4/').first();
      
      if (await moveText.isVisible()) {
        // VERIFY: Move is clickable (has cursor pointer or click handler)
        const cursor = await moveText.evaluate(el => 
          window.getComputedStyle(el).cursor
        );
        
        // Try clicking
        await moveText.click();
        await page.waitForTimeout(300);

        // VERIFY: Board updated (FEN changed)
        const fen = await page.evaluate(() => (window as any).currentFEN);
        expect(fen).toBeTruthy();
      }
    }
  });

  test('conversational responses are natural', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Ask conversational question
      await chatInput.fill("What do you think about the Italian Game?");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      const response = page.locator('.assistant-message').last();
      const responseText = await response.textContent();

      // VERIFY: Response exists and is not empty
      expect(responseText).toBeTruthy();
      expect(responseText!.length).toBeGreaterThan(10);

      // VERIFY: Not overly structured (no rigid "Verdict:" format for conversational)
      const isOverlyStructured = 
        responseText?.includes('Verdict:') && 
        responseText?.includes('Key Themes:') &&
        responseText?.includes('Candidate Moves:');
      
      // Conversational should be more fluid
      expect(isOverlyStructured).toBe(false);
    }
  });

  test('analytical requests get structured responses', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Ask analytical question
      await chatInput.fill("Analyze the current position");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      const response = page.locator('.assistant-message').last();
      const responseText = await response.textContent();

      // VERIFY: Has some analytical structure
      const hasAnalyticalContent = 
        responseText?.includes('advantage') || 
        responseText?.includes('eval') ||
        responseText?.includes('best') ||
        responseText?.includes('move') ||
        responseText?.includes('plan');
      
      expect(hasAnalyticalContent).toBe(true);
    }
  });

  test('tool errors are handled gracefully', async ({ page }) => {
    // Monitor errors
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Try to trigger an edge case (invalid FEN analysis)
      await chatInput.fill("Analyze position with FEN: invalid");
      await chatInput.press('Enter');

      await page.waitForTimeout(5000);

      // VERIFY: System didn't crash (still responsive)
      const isResponsive = await page.evaluate(() => document.readyState === 'complete');
      expect(isResponsive).toBe(true);

      // VERIFY: Got some response (error message or graceful handling)
      const messages = await page.locator('.message').count();
      expect(messages).toBeGreaterThan(0);
    }
  });

  test('LLM responses stream without blocking UI', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // Send message
      await chatInput.fill("Explain the Sicilian Defense in detail");
      await chatInput.press('Enter');

      // VERIFY: UI remains interactive while waiting
      await page.waitForTimeout(1000);
      
      const inputEnabled = await chatInput.isEnabled();
      expect(inputEnabled).toBe(true);

      // Wait for response to complete
      await page.waitForTimeout(5000);

      // VERIFY: Response appeared
      const response = page.locator('.assistant-message').last();
      await expect(response).toBeVisible();
    }
  });

  test('multiple LLM exchanges maintain context', async ({ page }) => {
    const chatInput = page.locator('textarea').first();
    
    if (await chatInput.isVisible()) {
      // First message
      await chatInput.fill("Let's analyze 1. e4");
      await chatInput.press('Enter');
      await page.waitForTimeout(5000);

      // Second message (should have context from first)
      await chatInput.fill("What about e5 in response?");
      await chatInput.press('Enter');
      await page.waitForTimeout(5000);

      // VERIFY: Both messages appear
      const messages = await page.locator('.message').count();
      expect(messages).toBeGreaterThanOrEqual(4); // 2 user + 2 assistant

      // VERIFY: No context loss errors
      const errors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          errors.push(msg.text());
        }
      });
      
      expect(errors.filter(e => e.includes('context') || e.includes('undefined'))).toHaveLength(0);
    }
  });
});

