"use client";

import { useState, useMemo } from "react";

interface OpeningLessonModalProps {
  open: boolean;
  onClose: () => void;
  currentFen: string;
  onStartLesson: (config: {
    openingQuery: string;
    startFromCurrent: boolean;
    orientation: "white" | "black";
  }) => void;
}

// Comprehensive list of chess openings
const ALL_OPENINGS = [
  // e4 openings
  "Sicilian Defense", "Sicilian Najdorf", "Sicilian Dragon", "Sicilian Scheveningen", "Sicilian Taimanov", "Sicilian Kan", "Sicilian Classical", "Sicilian Accelerated Dragon", "Sicilian Alapin", "Sicilian Closed", "Sicilian Four Knights", "Sicilian Grand Prix", "Sicilian Hyperaccelerated Dragon", "Sicilian Kalashnikov", "Sicilian Maroczy Bind", "Sicilian Moscow", "Sicilian O'Kelly", "Sicilian Pelikan", "Sicilian Pin", "Sicilian Richter-Rauzer", "Sicilian Rossolimo", "Sicilian Sveshnikov", "Sicilian Wing Gambit",
  "French Defense", "French Winawer", "French Tarrasch", "French Classical", "French Advance", "French Exchange", "French MacCutcheon", "French Rubinstein",
  "Caro-Kann Defense", "Caro-Kann Classical", "Caro-Kann Advance", "Caro-Kann Exchange", "Caro-Kann Panov-Botvinnik",
  "Scandinavian Defense", "Scandinavian Modern", "Scandinavian Classical",
  "Alekhine Defense", "Alekhine Four Pawns", "Alekhine Modern",
  "Pirc Defense", "Pirc Classical", "Pirc Austrian Attack",
  "King's Pawn Game", "Vienna Game", "Vienna Gambit", "Bishop's Opening", "King's Gambit", "King's Gambit Accepted", "King's Gambit Declined", "Latvian Gambit", "Philidor Defense", "Petrov Defense", "Russian Game", "Scotch Game", "Scotch Gambit", "Italian Game", "Italian Giuoco Piano", "Italian Two Knights", "Evans Gambit", "Ruy Lopez", "Spanish Game", "Ruy Lopez Berlin Defense", "Ruy Lopez Closed", "Ruy Lopez Exchange", "Ruy Lopez Morphy Defense", "Ruy Lopez Schliemann Defense", "Ruy Lopez Steinitz Defense",
  
  // d4 openings
  "Queen's Gambit", "Queen's Gambit Accepted", "Queen's Gambit Declined", "Queen's Gambit Slav Defense", "Queen's Gambit Tarrasch Defense", "Queen's Gambit Chigorin Defense", "Queen's Gambit Albin Countergambit", "Queen's Gambit Marshall Defense", "Queen's Gambit Semi-Slav", "Queen's Gambit Meran", "Queen's Gambit Botvinnik",
  "London System", "Trompowsky Attack", "Torre Attack", "Colle System", "Stonewall Attack",
  "King's Indian Defense", "King's Indian Classical", "King's Indian Fianchetto", "King's Indian Sämisch", "King's Indian Four Pawns", "King's Indian Averbakh", "King's Indian Makagonov", "King's Indian Petrosian",
  "Nimzo-Indian Defense", "Nimzo-Indian Classical", "Nimzo-Indian Rubinstein", "Nimzo-Indian Sämisch", "Nimzo-Indian Leningrad",
  "Grünfeld Defense", "Grünfeld Exchange", "Grünfeld Russian", "Grünfeld Fianchetto",
  "Benoni Defense", "Modern Benoni", "Benko Gambit", "Czech Benoni", "Old Benoni",
  "Catalan Opening", "Catalan Closed", "Catalan Open",
  "Dutch Defense", "Dutch Classical", "Dutch Leningrad", "Dutch Stonewall", "Dutch Staunton Gambit",
  "Bogo-Indian Defense", "Queen's Indian Defense", "Old Indian Defense",
  
  // Other openings
  "English Opening", "English Symmetrical", "English Four Knights", "English Reversed Sicilian", "English Botvinnik System",
  "Reti Opening", "Reti Gambit",
  "Nimzowitsch Defense", "Nimzowitsch-Larsen Attack",
  "Bird's Opening", "Polish Opening", "Sokolsky Opening",
  "King's Indian Attack", "King's Indian Reversed",
  "Modern Defense", "Robatsch Defense",
  "Owen's Defense", "St. George Defense",
  "Amar Opening", "Anderssen Opening", "Barnes Opening", "Clemenz Opening", "Desprez Opening", "Durkin Opening", "Grob Opening", "Mieses Opening", "Saragossa Opening", "Sodium Attack", "Van't Kruijs Opening", "Ware Opening",
  
  // ECO codes (common ones)
  "A00", "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18", "A19", "A20", "A21", "A22", "A23", "A24", "A25", "A26", "A27", "A28", "A29", "A30", "A31", "A32", "A33", "A34", "A35", "A36", "A37", "A38", "A39", "A40", "A41", "A42", "A43", "A44", "A45", "A46", "A47", "A48", "A49", "A50", "A51", "A52", "A53", "A54", "A55", "A56", "A57", "A58", "A59",
  "B00", "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19", "B20", "B21", "B22", "B23", "B24", "B25", "B26", "B27", "B28", "B29", "B30", "B31", "B32", "B33", "B34", "B35", "B36", "B37", "B38", "B39", "B40", "B41", "B42", "B43", "B44", "B45", "B46", "B47", "B48", "B49", "B50", "B51", "B52", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B60", "B61", "B62", "B63", "B64", "B65", "B66", "B67", "B68", "B69", "B70", "B71", "B72", "B73", "B74", "B75", "B76", "B77", "B78", "B79", "B80", "B81", "B82", "B83", "B84", "B85", "B86", "B87", "B88", "B89", "B90", "B91", "B92", "B93", "B94", "B95", "B96", "B97", "B98", "B99",
  "C00", "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19", "C20", "C21", "C22", "C23", "C24", "C25", "C26", "C27", "C28", "C29", "C30", "C31", "C32", "C33", "C34", "C35", "C36", "C37", "C38", "C39", "C40", "C41", "C42", "C43", "C44", "C45", "C46", "C47", "C48", "C49", "C50", "C51", "C52", "C53", "C54", "C55", "C56", "C57", "C58", "C59", "C60", "C61", "C62", "C63", "C64", "C65", "C66", "C67", "C68", "C69", "C70", "C71", "C72", "C73", "C74", "C75", "C76", "C77", "C78", "C79", "C80", "C81", "C82", "C83", "C84", "C85", "C86", "C87", "C88", "C89", "C90", "C91", "C92", "C93", "C94", "C95", "C96", "C97", "C98", "C99",
  "D00", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27", "D28", "D29", "D30", "D31", "D32", "D33", "D34", "D35", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47", "D48", "D49", "D50", "D51", "D52", "D53", "D54", "D55", "D56", "D57", "D58", "D59", "D60", "D61", "D62", "D63", "D64", "D65", "D66", "D67", "D68", "D69", "D70", "D71", "D72", "D73", "D74", "D75", "D76", "D77", "D78", "D79", "D80", "D81", "D82", "D83", "D84", "D85", "D86", "D87", "D88", "D89", "D90", "D91", "D92", "D93", "D94", "D95", "D96", "D97", "D98", "D99",
  "E00", "E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10", "E11", "E12", "E13", "E14", "E15", "E16", "E17", "E18", "E19", "E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27", "E28", "E29", "E30", "E31", "E32", "E33", "E34", "E35", "E36", "E37", "E38", "E39", "E40", "E41", "E42", "E43", "E44", "E45", "E46", "E47", "E48", "E49", "E50", "E51", "E52", "E53", "E54", "E55", "E56", "E57", "E58", "E59", "E60", "E61", "E62", "E63", "E64", "E65", "E66", "E67", "E68", "E69", "E70", "E71", "E72", "E73", "E74", "E75", "E76", "E77", "E78", "E79", "E80", "E81", "E82", "E83", "E84", "E85", "E86", "E87", "E88", "E89", "E90", "E91", "E92", "E93", "E94", "E95", "E96", "E97", "E98", "E99",
];

export default function OpeningLessonModal({
  open,
  onClose,
  currentFen,
  onStartLesson,
}: OpeningLessonModalProps) {
  const [openingQuery, setOpeningQuery] = useState("");
  const [startFromCurrent, setStartFromCurrent] = useState(false);
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [showDropdown, setShowDropdown] = useState(false);

  const isStartingPosition = currentFen === "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  // Filter openings based on search query
  const filteredOpenings = useMemo(() => {
    if (!openingQuery.trim()) {
      return [];
    }
    
    const query = openingQuery.toLowerCase().trim();
    const matches = ALL_OPENINGS.filter(opening => 
      opening.toLowerCase().includes(query)
    );
    
    // Sort by relevance (exact matches first, then by position of match)
    return matches.sort((a, b) => {
      const aLower = a.toLowerCase();
      const bLower = b.toLowerCase();
      const aStarts = aLower.startsWith(query);
      const bStarts = bLower.startsWith(query);
      
      if (aStarts && !bStarts) return -1;
      if (!aStarts && bStarts) return 1;
      
      return aLower.indexOf(query) - bLower.indexOf(query);
    }).slice(0, 5); // Top 5 only
  }, [openingQuery]);

  if (!open) return null;

  const handleStart = () => {
    if (!openingQuery.trim()) {
      return;
    }
    onStartLesson({
      openingQuery: openingQuery.trim(),
      startFromCurrent,
      orientation,
    });
    onClose();
  };

  const handleOpeningSelect = (opening: string) => {
    setOpeningQuery(opening);
    setShowDropdown(false);
  };

  return (
    <div className="game-setup-overlay">
      <div className="game-setup-modal">
        <div className="game-setup-header">
          <h2>Opening Lesson</h2>
          <button className="game-setup-close" onClick={onClose}>×</button>
        </div>

        <div className="game-setup-content">
          {/* Opening Selection */}
          <div className="game-setup-section">
            <h3>Select Opening</h3>
            <div className="opening-input-container">
              <input
                type="text"
                value={openingQuery}
                onChange={(e) => {
                  setOpeningQuery(e.target.value);
                  setShowDropdown(e.target.value.trim().length > 0);
                }}
                onFocus={() => {
                  if (openingQuery.trim().length > 0) {
                    setShowDropdown(true);
                  }
                }}
                onBlur={() => {
                  // Delay to allow click on dropdown item
                  setTimeout(() => setShowDropdown(false), 200);
                }}
                placeholder="Type opening name or ECO code (e.g., B90, Sicilian Najdorf)"
                className="opening-input"
              />
              {showDropdown && filteredOpenings.length > 0 && (
                <div className="opening-dropdown">
                  {filteredOpenings.map((opening) => (
                    <button
                      key={opening}
                      className="opening-dropdown-item"
                      onClick={() => handleOpeningSelect(opening)}
                      onMouseDown={(e) => e.preventDefault()} // Prevent blur
                    >
                      {opening}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Side Selection */}
          <div className="game-setup-section">
            <h3>Choose Your Side</h3>
            <div className="side-selection">
              <button
                className={`side-button ${orientation === "white" ? "active" : ""}`}
                onClick={() => setOrientation("white")}
              >
                White
              </button>
              <button
                className={`side-button ${orientation === "black" ? "active" : ""}`}
                onClick={() => setOrientation("black")}
              >
                Black
              </button>
            </div>
          </div>

          {/* Start From Options */}
          <div className="game-setup-section">
            <h3>Start From</h3>
            <div className="start-options">
              <button
                className={`start-option-button ${!startFromCurrent ? "active" : ""}`}
                onClick={() => setStartFromCurrent(false)}
              >
                Starting Position
              </button>
              <button
                className={`start-option-button ${startFromCurrent ? "active" : ""}`}
                onClick={() => setStartFromCurrent(true)}
                disabled={isStartingPosition}
                title={isStartingPosition ? "Already at starting position" : undefined}
              >
                Current Board
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="game-setup-actions">
            <button className="game-setup-cancel" onClick={onClose}>
              Cancel
            </button>
            <button 
              className="game-setup-start" 
              onClick={handleStart}
              disabled={!openingQuery.trim()}
            >
              Start Lesson
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
