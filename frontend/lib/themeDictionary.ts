/**
 * Theme Dictionary - Natural Language Keywords
 * Maps theme codes to all possible ways they might be mentioned
 */

export interface ThemeKeywords {
  code: string;
  primary: string[];      // Main keywords
  synonyms: string[];     // Alternate terms
  related: string[];      // Related concepts
  negations: string[];    // Negative forms
}

export const THEME_DICTIONARY: ThemeKeywords[] = [
  {
    code: 'S_CENTER_SPACE',
    primary: ['center', 'central', 'centre'],
    synonyms: ['middle', 'core', 'd4', 'e4', 'd5', 'e5'],
    related: ['space', 'control', 'occupy', 'dominate', 'command'],
    negations: ['lose center', 'give up center', 'abandon center', 'weak center']
  },
  {
    code: 'S_SPACE',
    primary: ['space', 'spatial'],
    synonyms: ['room', 'territory', 'area'],
    related: ['advantage', 'control', 'restrict', 'squeeze', 'cramp'],
    negations: ['cramped', 'restricted', 'no space', 'tight']
  },
  {
    code: 'S_PAWN',
    primary: ['pawn', 'pawns', 'pawn structure'],
    synonyms: ['pawn formation', 'pawn chain', 'pawn skeleton'],
    related: ['isolated', 'doubled', 'backward', 'passed', 'weak pawn', 'strong pawn', 'islands'],
    negations: ['bad pawns', 'weak structure']
  },
  {
    code: 'S_KING',
    primary: ['king safety', 'king', 'king security'],
    synonyms: ['king shelter', 'king protection', 'castled position'],
    related: ['safe', 'exposed', 'vulnerable', 'shield', 'pawn cover', 'attack on king'],
    negations: ['unsafe king', 'exposed king', 'weak king']
  },
  {
    code: 'S_ACTIVITY',
    primary: ['activity', 'piece activity', 'active'],
    synonyms: ['mobility', 'piece coordination', 'piece placement'],
    related: ['develop', 'activate', 'mobile', 'scope', 'range', 'flexible'],
    negations: ['passive', 'inactive', 'restricted', 'blocked']
  },
  {
    code: 'S_DEV',
    primary: ['development', 'develop', 'developing'],
    synonyms: ['mobilize', 'bring out', 'activate pieces'],
    related: ['undeveloped', 'tempo', 'piece out', 'get pieces out'],
    negations: ['undeveloped', 'behind in development', 'slow development']
  },
  {
    code: 'S_THREATS',
    primary: ['threat', 'threats', 'attacking', 'attack'],
    synonyms: ['pressure', 'tactical shot', 'danger', 'menace'],
    related: ['capture', 'fork', 'pin', 'skewer', 'hanging', 'undefended', 'trap'],
    negations: ['no threats', 'safe from threats']
  },
  {
    code: 'S_TACTICS',
    primary: ['tactic', 'tactics', 'tactical'],
    synonyms: ['combination', 'tactical blow', 'tactical shot'],
    related: ['fork', 'pin', 'skewer', 'discovery', 'sacrifice', 'trap', 'trick'],
    negations: ['no tactics', 'tactically safe']
  },
  {
    code: 'S_BREAKS',
    primary: ['break', 'pawn break', 'breakthrough'],
    synonyms: ['lever', 'pawn storm', 'advance'],
    related: ['push', 'burst', 'rupture', 'crack open'],
    negations: ['no breaks available']
  },
  {
    code: 'S_PROMOTION',
    primary: ['promotion', 'promote', 'promoting'],
    synonyms: ['queen', 'queening', 'passed pawn', 'runner'],
    related: ['advance', 'race', 'unstoppable', 'promote to'],
    negations: ['stopped promotion', 'blockaded']
  },
  {
    code: 'S_LANES',
    primary: ['file', 'diagonal', 'lane'],
    synonyms: ['open file', 'semi-open', 'long diagonal', 'highway'],
    related: ['penetrate', 'invasion', 'infiltrate', 'battery'],
    negations: ['closed file', 'blocked diagonal']
  },
  {
    code: 'S_COLOR_COMPLEX',
    primary: ['color complex', 'dark squares', 'light squares'],
    synonyms: ['square color', 'weak squares', 'dark square weakness'],
    related: ['bishop', 'hole', 'weak color', 'control squares'],
    negations: []
  },
  {
    code: 'S_TRADES',
    primary: ['trade', 'exchange', 'swap'],
    synonyms: ['simplify', 'liquidate', 'trade pieces', 'exchange pieces'],
    related: ['capture', 'recapture', 'trade down', 'simplification'],
    negations: ['avoid trades', 'keep pieces']
  },
  {
    code: 'S_PROPHYLAXIS',
    primary: ['prophylaxis', 'prevent', 'stop'],
    synonyms: ['restrain', 'control', 'restrict opponent'],
    related: ['block', 'deny', 'prevent plan', 'stop threat'],
    negations: []
  }
];

/**
 * Check if a theme is mentioned in the LLM's response
 */
export function isThemeMentioned(themeCode: string, llmText: string): boolean {
  const textLower = llmText.toLowerCase();
  const theme = THEME_DICTIONARY.find(t => t.code === themeCode);
  
  if (!theme) return false;
  
  // Check primary keywords
  for (const keyword of theme.primary) {
    if (textLower.includes(keyword.toLowerCase())) {
      return true;
    }
  }
  
  // Check synonyms
  for (const synonym of theme.synonyms) {
    if (textLower.includes(synonym.toLowerCase())) {
      return true;
    }
  }
  
  // Check related terms (need at least the theme concept + related)
  // e.g., "central" + "control" for S_CENTER_SPACE
  const hasThemeConcept = theme.primary.some(p => textLower.includes(p.toLowerCase()));
  if (hasThemeConcept) {
    for (const related of theme.related) {
      if (textLower.includes(related.toLowerCase())) {
        return true;
      }
    }
  }
  
  // Check negations (still counts as mentioning the theme)
  for (const negation of theme.negations) {
    if (textLower.includes(negation.toLowerCase())) {
      return true;
    }
  }
  
  return false;
}

/**
 * Filter themes to only those mentioned by LLM
 */
export function filterMentionedThemes(
  themes: string[],
  llmText: string
): string[] {
  return themes.filter(theme => isThemeMentioned(theme, llmText));
}

/**
 * Get all theme codes mentioned in LLM text
 */
export function extractMentionedThemes(llmText: string): string[] {
  const mentioned: string[] = [];
  
  for (const theme of THEME_DICTIONARY) {
    if (isThemeMentioned(theme.code, llmText)) {
      mentioned.push(theme.code);
    }
  }
  
  return mentioned;
}

/**
 * Check if a specific tag is mentioned
 */
export function isTagMentioned(tag: any, llmText: string): boolean {
  const textLower = llmText.toLowerCase();
  const tagName = (tag.tag_name || '').toLowerCase();
  
  // Tag keyword mapping
  const tagKeywords: Record<string, string[]> = {
    'threat.capture': ['attacking', 'attack', 'capture', 'threat', 'hanging', 'undefended'],
    'threat.fork': ['fork', 'double attack', 'attacks two', 'attacks both'],
    'threat.pin': ['pin', 'pinned', 'cannot move'],
    'threat.skewer': ['skewer', 'x-ray'],
    'outpost': ['outpost', 'strong square', 'stable square'],
    'file.open': ['open file', 'open lane'],
    'file.semi': ['semi-open', 'semi open', 'half-open'],
    'diagonal': ['diagonal', 'long diagonal', 'bishop diagonal'],
    'bishop.pair': ['bishop pair', 'two bishops', 'bishops'],
    'pawn.passed': ['passed pawn', 'passer', 'runner'],
    'pawn.isolated': ['isolated pawn', 'isolated'],
    'pawn.doubled': ['doubled pawn', 'doubled', 'pawn stack'],
    'pawn.backward': ['backward pawn', 'backward'],
    'king.exposed': ['exposed king', 'unsafe king', 'vulnerable king'],
    'king.shield': ['pawn shield', 'king shelter', 'king protection'],
    'tactic.fork': ['fork', 'double attack'],
    'tactic.pin': ['pin', 'pinned'],
    'piece.trapped': ['trapped', 'trapped piece', 'no squares']
  };
  
  // Check if any keywords match
  for (const [tagPattern, keywords] of Object.entries(tagKeywords)) {
    if (tagName.includes(tagPattern)) {
      for (const keyword of keywords) {
        if (textLower.includes(keyword)) {
          return true;
        }
      }
    }
  }
  
  // Also check if specific piece mentioned (e.g., "knight on c3")
  if (tag.pieces) {
    for (const piece of tag.pieces) {
      const square = piece.match(/[a-h][1-8]/)?.[0];
      if (square && textLower.includes(square)) {
        return true;
      }
    }
  }
  
  // Check if specific squares mentioned
  if (tag.squares) {
    for (const square of tag.squares) {
      if (textLower.includes(square.toLowerCase())) {
        return true;
      }
    }
  }
  
  return false;
}

