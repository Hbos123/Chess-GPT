/**
 * Emoji Filter - Removes all emoji from text
 * Applied to LLM responses and system messages for strict monochrome UI
 */

export function stripEmojis(text: string): string {
  if (!text) return text;
  
  return text
    // Emoticons
    .replace(/[\u{1F600}-\u{1F64F}]/gu, '')
    // Symbols & Pictographs
    .replace(/[\u{1F300}-\u{1F5FF}]/gu, '')
    // Transport & Map
    .replace(/[\u{1F680}-\u{1F6FF}]/gu, '')
    // Supplemental Symbols
    .replace(/[\u{1F900}-\u{1F9FF}]/gu, '')
    // Miscellaneous Symbols
    .replace(/[\u{2600}-\u{26FF}]/gu, '')
    // Dingbats
    .replace(/[\u{2700}-\u{27BF}]/gu, '')
    // Enclosed Alphanumerics
    .replace(/[\u{1F100}-\u{1F1FF}]/gu, '')
    // Flags
    .replace(/[\u{1F1E6}-\u{1F1FF}]/gu, '')
    // Chess symbols (optional - keep these?)
    // .replace(/[\u{2654}-\u{265F}]/gu, '')
    // Playing card symbols
    .replace(/[\u{1F0A0}-\u{1F0FF}]/gu, '')
    // Mahjong tiles
    .replace(/[\u{1F000}-\u{1F02F}]/gu, '')
    // Additional symbols
    .replace(/[\u{1F780}-\u{1F7FF}]/gu, '')
    // Geometric shapes (some might be emoji)
    .replace(/[\u{1F7E0}-\u{1F7EB}]/gu, '')
    // Extended pictographs
    .replace(/[\u{1FA70}-\u{1FAFF}]/gu, '')
    // Variation selectors (emoji modifiers)
    .replace(/[\u{FE00}-\u{FE0F}]/gu, '')
    .replace(/[\u{E0100}-\u{E01EF}]/gu, '')
    // Zero width joiner (used in emoji sequences)
    .replace(/\u{200D}/gu, '')
    // Common emoji combiners
    .replace(/[\u{20E3}\u{FE0F}\u{1F3FB}-\u{1F3FF}]/gu, '')
    // Trim any extra spaces created
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/**
 * Check if text contains any emoji
 */
export function containsEmoji(text: string): boolean {
  if (!text) return false;
  return text !== stripEmojis(text);
}

/**
 * Replace emoji with text alternatives
 * For cases where complete removal is too aggressive
 */
export function replaceEmojis(text: string): string {
  const replacements: Record<string, string> = {
    '✓': '[OK]',
    '✅': '[DONE]',
    '❌': '[X]',
    '⚠️': '[!]',
    '⚡': '[CRITICAL]',
    '📊': '[DATA]',
    '📍': '[VISUAL]',
    '🎯': '[TARGET]',
    '🔄': '[ANALYZING]',
    '📚': '[THEORY]',
    '♟️': '[MOVE]',
    '🎨': '[ANNOTATION]'
  };
  
  let result = text;
  for (const [emoji, replacement] of Object.entries(replacements)) {
    result = result.replace(new RegExp(emoji, 'g'), replacement);
  }
  
  return stripEmojis(result);
}

