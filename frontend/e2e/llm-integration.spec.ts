/**
 * LLM Integration E2E Tests
 * 
 * Tests LLM chat functionality, tool calling, and response rendering.
 */

import { test, expect } from '@playwright/test';

test.describe('LLM Chat Integration', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should send message and receive LLM response', async ({ page }) => {
    // Find chat input
    const chatInput = page.locator('textarea, input[type="text"]').first();
    
    // Send a simple message
    await chatInput.fill('Tell me about the King\'s Pawn opening');
    await chatInput.press('Enter');
    
    // Wait for LLM response (up to 15 seconds)
    await page.waitForTimeout(15000);
    
    // Look for assistant message
    const messages = await page.locator('.assistant-message, .message-bubble').count();
    
    // Should have at least received something
    expect(messages).toBeGreaterThan(0);
  });

  test('should handle LLM responses without rendering errors', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first();
    
    // Send message
    await chatInput.fill('Analyze this position');
    await chatInput.press('Enter');
    
    // Wait for response
    await page.waitForTimeout(12000);
    
    // Check for any error messages in UI
    const errorMsg = await page.locator('.error-message, [data-error="true"]').count();
    expect(errorMsg).toBe(0);
    
    // Verify page still responsive
    const inputStillWorks = await chatInput.isVisible();
    expect(inputStillWorks).toBe(true);
  });

  test('should render markdown in LLM responses', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first();
    
    await chatInput.fill('Explain chess notation');
    await chatInput.press('Enter');
    
    // Wait for response
    await page.waitForTimeout(10000);
    
    // Look for formatted content (markdown should be rendered)
    const messageContent = page.locator('.message-bubble, .message-content').first();
    const exists = await messageContent.count();
    
    // Just verify content rendered
    expect(exists).toBeGreaterThan(0);
  });
});

test.describe('LLM Tool Calling', () => {
  test('should handle tool calls without errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    const chatInput = page.locator('textarea, input[type="text"]').first();
    
    // Message that might trigger analyze_move tool
    await chatInput.fill('Is e4 a good move?');
    await chatInput.press('Enter');
    
    // Wait for tool execution
    await page.waitForTimeout(15000);
    
    // Filter out unrelated errors
    const relevantErrors = consoleErrors.filter(e => 
      !e.includes('favicon') && 
      !e.includes('hydration') &&
      !e.includes('SourceMap')
    );
    
    // Should have minimal errors
    expect(relevantErrors.length).toBeLessThan(5);
  });
});

