// Move Tree Data Structure for handling variations and comments
// Supports nested variations, inline comments, and tree navigation

export interface MoveNode {
  id: string;
  moveNumber: number;
  move: string;  // SAN notation
  fen: string;   // Position after this move
  comment?: string;
  nags?: string[];  // Numeric Annotation Glyphs (!!, ?, etc.)
  parent: MoveNode | null;
  children: MoveNode[];  // First child is main line, rest are variations
  isMainLine: boolean;
}

export class MoveTree {
  root: MoveNode;
  currentNode: MoveNode;
  
  constructor() {
    this.root = {
      id: 'root',
      moveNumber: 0,
      move: '',
      fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      parent: null,
      children: [],
      isMainLine: true,
    };
    this.currentNode = this.root;
  }

  // Add a move to the current position
  addMove(move: string, fen: string, comment?: string): MoveNode {
    const existingChild = this.currentNode.children.find(
      (child) => child.move === move
    );

    if (existingChild) {
      this.currentNode = existingChild;
      if (comment) {
        existingChild.comment = comment;
      }
      return existingChild;
    }

    const isWhiteMove = fen.split(' ')[1] === 'b';
    const moveNumber = isWhiteMove
      ? this.currentNode.moveNumber + 1
      : this.currentNode.moveNumber;

    const newNode: MoveNode = {
      id: `${this.currentNode.id}-${move}-${Date.now()}`,
      moveNumber,
      move,
      fen,
      comment,
      parent: this.currentNode,
      children: [],
      isMainLine: this.currentNode.children.length === 0, // First child is main line
    };

    this.currentNode.children.push(newNode);
    this.currentNode = newNode;
    return newNode;
  }

  // Navigate to a specific node (finds matching node by ID if from different tree)
  goToNode(node: MoveNode) {
    // If node is from this tree, use it directly
    if (this.findNodeById(node.id)) {
      const foundNode = this.findNodeById(node.id);
      if (foundNode) {
        this.currentNode = foundNode;
        return;
      }
    }
    
    // Fallback: use the node as-is (might be from same tree)
    this.currentNode = node;
  }
  
  // Find node by ID in this tree
  findNodeById(id: string): MoveNode | null {
    return this.searchNodeById(this.root, id);
  }
  
  /**
   * Find a node by ply index along the main line.
   * Ply 0 refers to the root position (before any moves).
   * Ply 1 refers to the first move node in the main line, etc.
   */
  findNodeByPly(ply: number): MoveNode | null {
    const p = Math.max(0, Math.floor(ply));
    if (p === 0) return this.root;
    const main = this.getMainLine();
    return main[p - 1] ?? null;
  }
  
  private searchNodeById(node: MoveNode, id: string): MoveNode | null {
    if (node.id === id) return node;
    
    for (const child of node.children) {
      const found = this.searchNodeById(child, id);
      if (found) return found;
    }
    
    return null;
  }

  // Navigate to previous move
  goBack(): MoveNode | null {
    if (this.currentNode.parent) {
      this.currentNode = this.currentNode.parent;
      return this.currentNode;
    }
    return null;
  }

  // Navigate to next move (main line)
  goForward(): MoveNode | null {
    if (this.currentNode.children.length > 0) {
      this.currentNode = this.currentNode.children[0];
      return this.currentNode;
    }
    return null;
  }

  // Navigate to start
  goToStart() {
    this.currentNode = this.root;
  }

  // Navigate to end (of main line)
  goToEnd() {
    while (this.currentNode.children.length > 0) {
      this.currentNode = this.currentNode.children[0];
    }
  }

  // Delete current move and all following moves
  deleteMove(): MoveNode | null {
    const parent = this.currentNode.parent;
    if (!parent) return null;

    const index = parent.children.indexOf(this.currentNode);
    if (index > -1) {
      parent.children.splice(index, 1);
    }

    this.currentNode = parent;
    return parent;
  }

  // Delete entire variation (removes this move and siblings after it)
  deleteVariation(): MoveNode | null {
    const parent = this.currentNode.parent;
    if (!parent) return null;

    const index = parent.children.indexOf(this.currentNode);
    if (index > 0) {
      // Only delete if it's not the main line (index 0)
      parent.children.splice(index, 1);
      this.currentNode = parent;
      return parent;
    } else if (index === 0 && parent.children.length > 1) {
      // If it's main line but has siblings, promote first variation
      parent.children.shift();
      this.currentNode = parent;
      return parent;
    }

    return null;
  }

  // Promote variation to main line
  promoteVariation(): boolean {
    const parent = this.currentNode.parent;
    if (!parent) return false;

    const index = parent.children.indexOf(this.currentNode);
    if (index > 0) {
      // Move this child to position 0 (main line)
      const node = parent.children.splice(index, 1)[0];
      parent.children.unshift(node);
      node.isMainLine = true;
      
      // Update old main line
      if (parent.children.length > 1) {
        parent.children[1].isMainLine = false;
      }
      
      return true;
    }

    return false;
  }

  // Add comment to current move
  addComment(comment: string) {
    this.currentNode.comment = comment;
  }

  // Get all moves in current variation
  getCurrentLine(): MoveNode[] {
    const line: MoveNode[] = [];
    let node: MoveNode | null = this.currentNode;

    while (node && node.parent) {
      line.unshift(node);
      node = node.parent;
    }

    return line;
  }

  // Get main line from root
  getMainLine(): MoveNode[] {
    const line: MoveNode[] = [];
    let node = this.root.children[0];

    while (node) {
      line.push(node);
      node = node.children[0];
    }

    return line;
  }

  // Convert tree to PGN string
  toPGN(): string {
    return this.nodeToPGN(this.root, true);
  }

  private nodeToPGN(node: MoveNode, isRoot: boolean = false): string {
    let pgn = '';
    
    if (!isRoot && node.move) {
      // Add move number for white moves or start of variation
      const needsMoveNumber = node.fen.split(' ')[1] === 'b' || 
                              (node.parent?.children[0] !== node);
      
      if (needsMoveNumber) {
        pgn += `${node.moveNumber}. `;
      } else if (node.fen.split(' ')[1] === 'w') {
        pgn += `${node.moveNumber}... `;
      }
      
      pgn += node.move + ' ';
      
      // Add comment if exists
      if (node.comment) {
        pgn += `{${node.comment}} `;
      }
    }

    // Process children
    if (node.children.length > 0) {
      // Main line (first child)
      pgn += this.nodeToPGN(node.children[0], false);
      
      // Variations (other children)
      for (let i = 1; i < node.children.length; i++) {
        pgn += `(${this.nodeToPGN(node.children[i], false).trim()}) `;
      }
    }

    return pgn;
  }

  // Parse PGN into move tree
  static fromPGN(pgnString: string): MoveTree {
    const tree = new MoveTree();
    if (!pgnString || !pgnString.trim()) {
      return tree;
    }

    try {
      // Use Chess.js to parse the PGN
      const { Chess } = require('chess.js');
      const game = new Chess();
      
      // Load PGN - this will parse the moves
      game.loadPgn(pgnString);
      
      // Build move tree by replaying the game
      const history = game.history({ verbose: true });
      let currentNode = tree.root;
      
      // Replay moves one by one to build the tree
      const replayGame = new Chess();
      for (const move of history) {
        const moveResult = replayGame.move(move.san);
        if (moveResult) {
          const fen = replayGame.fen();
          currentNode = tree.addMove(move.san, fen);
        }
      }
      
      // Set current node to the last move
      tree.currentNode = currentNode;
      
      return tree;
    } catch (error) {
      console.error('[MoveTree.fromPGN] Error parsing PGN:', error);
      console.error('[MoveTree.fromPGN] PGN preview:', pgnString.substring(0, 200));
      // Return empty tree on error
      return tree;
    }
  }

  // Get path from root to current node
  getPath(): string[] {
    const path: string[] = [];
    let node: MoveNode | null = this.currentNode;

    while (node && node.parent) {
      const index = node.parent.children.indexOf(node);
      path.unshift(index.toString());
      node = node.parent;
    }

    return path;
  }

  // Clone the tree
  clone(): MoveTree {
    const newTree = new MoveTree();
    newTree.root = this.cloneNode(this.root, null);
    
    // Find corresponding current node in cloned tree
    const path = this.getPath();
    let node = newTree.root;
    for (const index of path) {
      const idx = parseInt(index);
      if (node.children[idx]) {
        node = node.children[idx];
      }
    }
    newTree.currentNode = node;
    
    return newTree;
  }

  private cloneNode(node: MoveNode, parent: MoveNode | null): MoveNode {
    const cloned: MoveNode = {
      id: node.id,
      moveNumber: node.moveNumber,
      move: node.move,
      fen: node.fen,
      comment: node.comment,
      nags: node.nags ? [...node.nags] : undefined,
      parent,
      children: [],
      isMainLine: node.isMainLine,
    };

    cloned.children = node.children.map((child) => this.cloneNode(child, cloned));
    
    return cloned;
  }
}

