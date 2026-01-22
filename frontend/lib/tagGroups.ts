/**
 * Tag grouping system for chess habits.
 * Groups related tags (e.g., all open files) and provides human-readable display names.
 */

import type { Habit } from './api';

// Tag group definitions
export interface TagGroup {
  displayName: string;
  description: string;
  patterns: string[];
  color: string;
}

export const TAG_GROUPS: Record<string, TagGroup> = {
  file_open: {
    displayName: 'Open Files',
    description: 'Files with no pawns from either side',
    patterns: ['tag.file.open'],
    color: '#3b82f6',
  },
  file_semi: {
    displayName: 'Semi-Open Files',
    description: 'Files with only opponent pawns',
    patterns: ['tag.file.semi'],
    color: '#60a5fa',
  },
  diagonal_open: {
    displayName: 'Open Diagonals',
    description: 'Long unblocked diagonal lines',
    patterns: ['tag.diagonal.open', 'tag.diagonal.long'],
    color: '#8b5cf6',
  },
  king_safety: {
    displayName: 'King Safety',
    description: 'King exposure, attackers, and shield',
    patterns: ['tag.king.attackers', 'tag.king.defenders', 'tag.king.shield', 'tag.king.file'],
    color: '#ef4444',
  },
  center_control: {
    displayName: 'Center Control',
    description: 'Control of central squares d4, d5, e4, e5',
    patterns: ['tag.center', 'tag.key.d4', 'tag.key.d5', 'tag.key.e4', 'tag.key.e5'],
    color: '#f59e0b',
  },
  rook_play: {
    displayName: 'Rook Activity',
    description: 'Rook positioning, open files, and coordination',
    patterns: ['tag.rook'],
    color: '#10b981',
  },
  bishop_play: {
    displayName: 'Bishop Play',
    description: 'Bishop effectiveness and pair advantage',
    patterns: ['tag.bishop'],
    color: '#06b6d4',
  },
  piece_activity: {
    displayName: 'Piece Mobility',
    description: 'Overall piece activity and movement options',
    patterns: ['tag.activity.mobility'],
    color: '#ec4899',
  },
  space: {
    displayName: 'Space Control',
    description: 'Territorial advantage on the board',
    patterns: ['tag.space'],
    color: '#84cc16',
  },
  trapped_pieces: {
    displayName: 'Piece Safety',
    description: 'Trapped, hanging, or vulnerable pieces',
    patterns: ['tag.piece.trapped', 'tag.piece.hanging'],
    color: '#f97316',
  },
  phase: {
    displayName: 'Game Phase',
    description: 'Opening, middlegame, and endgame performance',
    patterns: ['phase_'],
    color: '#6366f1',
  },
} as const;

// Display name mappings for specific tag patterns
const DISPLAY_MAP: Record<string, string> = {
  // File patterns
  'file.open': 'Open',
  'file.semi': 'Semi-Open',
  
  // Diagonal patterns
  'diagonal.open': 'Open Diagonal',
  'diagonal.long': 'Long Diagonal',
  
  // King safety
  'king.attackers.count': 'King Attackers',
  'king.defenders.count': 'King Defenders',
  'king.shield.missing': 'Missing King Shield',
  'king.file.open': 'Open King File',
  'king.file.semi': 'Semi-Open King File',
  
  // Center control
  'center.control.core': 'Core Center Control',
  'center.control.near': 'Extended Center',
  
  // Rook play
  'rook.connected': 'Connected Rooks',
  'rook.semi_open': 'Rook on Semi-Open File',
  'rook.open_file': 'Rook on Open File',
  'rook.rank7': 'Rook on 7th Rank',
  
  // Bishop play
  'bishop.pair': 'Bishop Pair',
  'bishop.bad': 'Bad Bishop',
  'bishop.good': 'Good Bishop',
  'bishop.fianchetto': 'Fianchettoed Bishop',
  
  // Activity
  'activity.mobility.knight': 'Knight Mobility',
  'activity.mobility.bishop': 'Bishop Mobility',
  'activity.mobility.rook': 'Rook Mobility',
  'activity.mobility.queen': 'Queen Mobility',
  
  // Space
  'space.advantage': 'Space Advantage',
  
  // Piece safety
  'piece.trapped': 'Trapped Piece',
  'piece.hanging': 'Hanging Piece',
  
  // Phases
  'phase_opening': 'Opening Phase',
  'phase_middlegame': 'Middlegame Phase',
  'phase_endgame': 'Endgame Phase',
};

/**
 * Convert a raw tag name to a human-readable format.
 * e.g., "tag.file.semi.d" -> "Semi-Open D-File"
 * e.g., "tag.diagonal.open.c1_h6" -> "Open c1-h6 Diagonal"
 */
export function formatTagName(rawTag: string): string {
  // Handle phase habits
  if (rawTag.startsWith('phase_')) {
    const phase = rawTag.replace('phase_', '');
    return `${phase.charAt(0).toUpperCase()}${phase.slice(1)} Phase`;
  }
  
  // Remove "tag." prefix if present
  const normalized = rawTag.toLowerCase().replace(/^tag\./, '');
  const parts = normalized.split('.');
  
  // Check for exact matches in display map
  const tagPath = parts.join('.');
  if (DISPLAY_MAP[tagPath]) {
    return DISPLAY_MAP[tagPath];
  }
  
  // Check for partial matches (e.g., "file.open" matches "file.open.d")
  for (const [pattern, display] of Object.entries(DISPLAY_MAP)) {
    if (tagPath.startsWith(pattern + '.')) {
      const suffix = tagPath.slice(pattern.length + 1);
      
      // Handle file specifics (e.g., file.semi.d -> "Semi-Open D-File")
      if (pattern.startsWith('file.')) {
        return `${display} ${suffix.toUpperCase()}-File`;
      }
      
      // Handle diagonal specifics (e.g., diagonal.open.c1_h6 -> "Open c1-h6 Diagonal")
      if (pattern.startsWith('diagonal.')) {
        const squares = suffix.replace('_', '-');
        return `${display} ${squares}`;
      }
      
      return `${display} (${suffix})`;
    }
  }
  
  // Handle key squares (e.g., key.e5 -> "e5 Control")
  if (parts[0] === 'key' && parts.length >= 2) {
    return `${parts[1].toUpperCase()} Control`;
  }
  
  // Handle file patterns without exact match
  if (parts[0] === 'file' && parts.length >= 3) {
    const type = parts[1] === 'open' ? 'Open' : 'Semi-Open';
    const file = parts[2].toUpperCase();
    return `${type} ${file}-File`;
  }
  
  // Handle diagonal patterns without exact match
  if (parts[0] === 'diagonal' && parts.length >= 3) {
    const type = parts[1] === 'open' ? 'Open' : parts[1] === 'long' ? 'Long' : parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
    const squares = parts[2].replace('_', '-');
    return `${type} ${squares} Diagonal`;
  }
  
  // Fallback: Title case with cleanup
  return parts
    .map(p => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
    .replace(/_/g, '-');
}

/**
 * Find which group a tag belongs to.
 * Returns the group key or null if no match.
 */
export function getTagGroup(tagName: string): string | null {
  const normalized = tagName.toLowerCase();
  
  for (const [groupKey, group] of Object.entries(TAG_GROUPS)) {
    if (group.patterns.some(pattern => normalized.includes(pattern.toLowerCase()))) {
      return groupKey;
    }
  }
  
  return null;
}

/**
 * Get the TagGroup object for a given tag name.
 */
export function getTagGroupInfo(tagName: string): TagGroup | null {
  const groupKey = getTagGroup(tagName);
  return groupKey ? TAG_GROUPS[groupKey] : null;
}

/**
 * Group habits by their tag category.
 * Returns a Map of group key -> habits array.
 */
export function groupHabitsByCategory(habits: Habit[]): Map<string, Habit[]> {
  const groups = new Map<string, Habit[]>();
  
  for (const habit of habits) {
    const group = getTagGroup(habit.name) || 'other';
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push(habit);
  }
  
  return groups;
}

/**
 * Get all habits in the same group as the given habit.
 */
export function getSameGroupHabits(habit: Habit, allHabits: Habit[]): Habit[] {
  const group = getTagGroup(habit.name);
  if (!group) return [];
  
  return allHabits.filter(h => 
    h.name !== habit.name && getTagGroup(h.name) === group
  );
}

/**
 * Calculate the average accuracy for a group of habits (current snapshot).
 */
export function calculateGroupAverage(habits: Habit[]): number | null {
  if (habits.length === 0) return null;
  
  const totalWeighted = habits.reduce((sum, h) => sum + h.accuracy * h.sample_size, 0);
  const totalSamples = habits.reduce((sum, h) => sum + h.sample_size, 0);
  
  return totalSamples > 0 ? totalWeighted / totalSamples : null;
}

/**
 * Calculate the group average sparkline (over time).
 * Aligns sparklines and averages them point-by-point.
 */
export function calculateGroupSparkline(habits: Habit[]): number[] | null {
  if (habits.length === 0) return null;
  
  // Get all sparklines, filtering out empty ones
  const sparklines = habits
    .map(h => h.sparkline)
    .filter(s => s && s.length > 0);
  
  if (sparklines.length === 0) return null;
  
  // Find the max length (most data points)
  const maxLen = Math.max(...sparklines.map(s => s.length));
  
  // For each point in time, average all available values
  const averaged: number[] = [];
  for (let i = 0; i < maxLen; i++) {
    const values: number[] = [];
    for (const sparkline of sparklines) {
      // Align from the right (most recent)
      const idx = sparkline.length - (maxLen - i);
      if (idx >= 0 && idx < sparkline.length) {
        values.push(sparkline[idx]);
      }
    }
    if (values.length > 0) {
      averaged.push(values.reduce((a, b) => a + b, 0) / values.length);
    }
  }
  
  return averaged.length > 0 ? averaged : null;
}

/**
 * Calculate baseline sparkline from all habits (overall accuracy over time).
 * This represents the user's average accuracy per game/time period.
 */
export function calculateBaselineSparkline(habits: Habit[]): number[] | null {
  // The baseline should be the average of ALL habits' sparklines
  // This gives us the user's overall accuracy trend over time
  return calculateGroupSparkline(habits);
}

