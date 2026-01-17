# Investigation PGN Documentation

*Generated: 2025-12-23 07:10:12*

## PGN Headers

- **Event**: Investigation
- **Site**: ?
- **Date**: ????.??.??
- **Round**: ?
- **White**: ?
- **Black**: ?
- **Result**: *
- **FEN**: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1

## Starting Position

**Tags**: [Starting tags: tag.king.attackers.count, tag.king.defenders.count, tag.king.attackers.count, tag.king.defenders.count, tag.activity.mobility.knight, tag.activity.mobility.bishop, tag.activity.mobility.rook, tag.activity.mobility.queen, tag.bishop.pair, tag.activity.mobility.knight, tag.activity.mobility.bishop, tag.activity.mobility.rook, tag.activity.mobility.queen, tag.bishop.pair]

## Main Line (Principal Variation)

**1. e4** *(Eval: +0.37, Theme: center_space,pawn_structure, Tactic: center control near)*
  - **Tag Changes:**
    - Gained: tag.center.control.near, tag.key.e4, tag.key.d5, tag.diagonal.open.f1-a6, tag.diagonal.open.d1-h5
    - Threats: center control near, key e4, key d5, diagonal open f1-a6, diagonal open d1-h5
  - **Branches:**
    - e5 (Eval: +0.25) - center_space,pawn_structure
      *[%eval +0.25] [%theme "center_space,pawn_structure"] [%tactic "key d4"] {[gained: tag.key.d4, tag.key.e5, tag.diagonal.open.f8-a3, tag.diagonal.open.d8-h4], [lost: none], [threats: key d4, key e5, diagonal open f8-a3, diagonal open d8-h4]*

**2. e5** *(Eval: +0.25, Theme: center_space,pawn_structure, Tactic: key d4)*
  - **Tag Changes:**
    - Gained: tag.key.d4, tag.key.e5, tag.diagonal.open.f8-a3, tag.diagonal.open.d8-h4
    - Threats: key d4, key e5, diagonal open f8-a3, diagonal open d8-h4
  - **Branches:**
    - Nf3 (Eval: +0.36) - center_space,piece_activity
      *[%eval +0.36] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core], [lost: tag.key.d4, tag.diagonal.open.d1-h5], [threats: center control core]*

**3. Nf3** *(Eval: +0.36, Theme: center_space,piece_activity, Tactic: center control core)*
  - **Tag Changes:**
    - Gained: tag.center.control.core
    - Lost: tag.key.d4, tag.diagonal.open.d1-h5
    - Threats: center control core
  - **Branches:**
    - Nf6 (Eval: +0.25) - center_space,piece_activity
      *[%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4], [threats: none]*

**4. Nf6** *(Eval: +0.25, Theme: center_space,piece_activity)*
  - **Tag Changes:**
    - Lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4
  - **Branches:**
    - d4 (Eval: +0.34) - center_space,piece_activity
      *[%eval +0.34] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4], [lost: none], [threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4]*

**5. d4** *(Eval: +0.34, Theme: center_space,piece_activity, Tactic: center control core)*
  - **Tag Changes:**
    - Gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4
    - Threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4
  - **Branches:**
    - Nxe4 (Eval: +0.25) - center_space,piece_activity
      *[%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped]*

**6. Nxe4** *(Eval: +0.25, Theme: center_space,piece_activity, Tactic: king file semi)*
  - **Tag Changes:**
    - Gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped
    - Lost: tag.center.control.near
    - Threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped
  - **Branches:**
    - Nxe5 (Eval: +0.32) - center_space,pawn_structure
      *[%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]*

**7. Nxe5** *(Eval: +0.32, Theme: center_space,pawn_structure, Tactic: king file open)*
  - **Tag Changes:**
    - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
    - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
    - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5
  - **Branches:**
    - d5 (Eval: +0.25) - center_space,piece_activity
      *[%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]*

**8. d5** *(Eval: +0.25, Theme: center_space,piece_activity, Tactic: key d5)*
  - **Tag Changes:**
    - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
    - Threats: key d5, diagonal open c8-h3, color hole dark d7
  - **Branches:**
    - Nd2 (Eval: +0.41) - center_space,piece_activity
      *[%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]*

**9. Nd2** *(Eval: +0.41, Theme: center_space,piece_activity)*
  - **Tag Changes:**
    - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2
  - **Branches:**
    - Nd7 (Eval: +0.38) - piece_activity,pawn_structure
      *[%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]*

**10. Nd7** *(Eval: +0.38, Theme: piece_activity,pawn_structure)*
  - **Tag Changes:**
    - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - **Branches:**
    - Nxe4 (Eval: +0.33) - center_space,piece_activity
      *[%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]*

**11. Nxe4** *(Eval: +0.33, Theme: center_space,piece_activity, Tactic: center control near)*
  - **Tag Changes:**
    - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
    - Threats: center control near, space advantage, diagonal open c1-h6
  - **Branches:**
    - dxe4 (Eval: +0.46) - center_space,piece_activity
      *[%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]*

**12. dxe4** *(Eval: +0.46, Theme: center_space,piece_activity, Tactic: king file semi)*
  - **Tag Changes:**
    - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
    - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
    - Threats: king file semi, king file semi, file semi d, file semi e
  - **Branches:**
    - Qh5 (Eval: +0.19) - center_space,piece_activity
      *[%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]*

**13. Qh5** *(Eval: +0.19, Theme: center_space,piece_activity, Tactic: diagonal open h5-d1)*
  - **Tag Changes:**
    - Gained: tag.diagonal.open.h5-d1
    - Lost: tag.diagonal.open.d1-h5
    - Threats: diagonal open h5-d1
  - **Branches:**
    - g6 (Eval: -0.08) - center_space,piece_activity
      *[%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]*

**14. g6** *(Eval: -0.08, Theme: center_space,piece_activity, Tactic: diagonal open f8-h6)*
  - **Tag Changes:**
    - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
    - Threats: diagonal open f8-h6, bishop bad
  - **Branches:**
    - Qe2 (Eval: +0.31) - center_space,piece_activity
      *[%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]*

**15. Qe2** *(Eval: +0.31, Theme: center_space,piece_activity, Tactic: diagonal open e2-h5)*
  - **Tag Changes:**
    - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
    - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
    - Threats: diagonal open e2-h5, diagonal open e2-a6
  - **Branches:**
    - Nxe5 (Eval: -0.05) - center_space,piece_activity
      *[%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]*

**16. Nxe5** *(Eval: -0.05, Theme: center_space,piece_activity, Tactic: center control core)*
  - **Tag Changes:**
    - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
    - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
    - Threats: center control core, center control core, key d5, diagonal open c8-h3
  - **Branches:**
    - Qxe4 (Eval: +0.31) - center_space,piece_activity
      *[%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]*

**17. Qxe4** *(Eval: +0.31, Theme: center_space,piece_activity, Tactic: king file open)*
  - **Tag Changes:**
    - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
    - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
    - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6
  - **Branches:**
    - Bg7 (Eval: +0.21) - center_space,piece_activity
      *[%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]*

**18. Bg7** *(Eval: +0.21, Theme: center_space,piece_activity, Tactic: center control near)*
  - **Tag Changes:**
    - Gained: tag.center.control.near
    - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
    - Threats: center control near
  - **Branches:**
    - dxe5 (Eval: -0.02) - center_space,piece_activity
      *[%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]*

**19. dxe5** *(Eval: -0.02, Theme: center_space,piece_activity, Tactic: file open d)*
  - **Tag Changes:**
    - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
    - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
    - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

## Alternate Branches

These are moves that were explored as variations (overestimated moves or stopped branches).

### Branch 1: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 2: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 3: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 4: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 5: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 6: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 7: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 8: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 9: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 10: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 11: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 12: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 13: Nxe5

- **Evaluation**: +0.32
- **Theme**: center_space,pawn_structure
- **Tactic**: king file open
- **Comment**: [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
  - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
  - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5

### Branch 14: Nxe4

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped
  - Lost: tag.center.control.near
  - Threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped

### Branch 15: d4

- **Evaluation**: +0.34
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval +0.34] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4], [lost: none], [threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4
  - Threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4

### Branch 16: Nf6

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4

### Branch 17: Nf3

- **Evaluation**: +0.36
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval +0.36] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core], [lost: tag.key.d4, tag.diagonal.open.d1-h5], [threats: center control core]
- **Tag Changes:**
  - Gained: tag.center.control.core
  - Lost: tag.key.d4, tag.diagonal.open.d1-h5
  - Threats: center control core

### Branch 18: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 19: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 20: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 21: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 22: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 23: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 24: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 25: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 26: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 27: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 28: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 29: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 30: Nxe5

- **Evaluation**: +0.32
- **Theme**: center_space,pawn_structure
- **Tactic**: king file open
- **Comment**: [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
  - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
  - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5

### Branch 31: Nxe4

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped
  - Lost: tag.center.control.near
  - Threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped

### Branch 32: d4

- **Evaluation**: +0.34
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval +0.34] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4], [lost: none], [threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4
  - Threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4

### Branch 33: Nf6

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4

### Branch 34: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 35: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 36: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 37: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 38: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 39: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 40: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 41: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 42: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 43: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 44: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 45: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 46: Nxe5

- **Evaluation**: +0.32
- **Theme**: center_space,pawn_structure
- **Tactic**: king file open
- **Comment**: [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
  - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
  - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5

### Branch 47: Nxe4

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped
  - Lost: tag.center.control.near
  - Threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped

### Branch 48: d4

- **Evaluation**: +0.34
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval +0.34] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4], [lost: none], [threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4
  - Threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4

### Branch 49: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 50: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 51: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 52: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 53: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 54: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 55: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 56: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 57: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 58: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 59: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 60: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 61: Nxe5

- **Evaluation**: +0.32
- **Theme**: center_space,pawn_structure
- **Tactic**: king file open
- **Comment**: [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
  - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
  - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5

### Branch 62: Nxe4

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped
  - Lost: tag.center.control.near
  - Threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped

### Branch 63: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 64: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 65: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 66: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 67: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 68: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 69: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 70: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 71: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 72: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 73: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 74: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 75: Nxe5

- **Evaluation**: +0.32
- **Theme**: center_space,pawn_structure
- **Tactic**: king file open
- **Comment**: [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5
  - Lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4
  - Threats: king file open, king file open, center control near, file open e, diagonal open d1-h5

### Branch 76: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 77: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 78: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 79: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 80: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 81: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 82: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 83: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 84: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 85: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 86: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 87: d5

- **Evaluation**: +0.25
- **Theme**: center_space,piece_activity
- **Tactic**: key d5
- **Comment**: [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7]
- **Tag Changes:**
  - Gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7
  - Threats: key d5, diagonal open c8-h3, color hole dark d7

### Branch 88: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 89: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 90: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 91: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 92: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 93: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 94: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 95: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 96: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 97: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 98: Nd2

- **Evaluation**: +0.41
- **Theme**: center_space,piece_activity
- **Comment**: [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2

### Branch 99: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 100: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 101: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 102: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 103: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 104: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 105: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 106: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 107: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 108: Nd7

- **Evaluation**: +0.38
- **Theme**: piece_activity,pawn_structure
- **Comment**: [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none]
- **Tag Changes:**
  - Lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7

### Branch 109: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 110: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 111: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 112: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 113: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 114: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 115: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 116: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 117: Nxe4

- **Evaluation**: +0.33
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6]
- **Tag Changes:**
  - Gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6
  - Threats: center control near, space advantage, diagonal open c1-h6

### Branch 118: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 119: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 120: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 121: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 122: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 123: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 124: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 125: dxe4

- **Evaluation**: +0.46
- **Theme**: center_space,piece_activity
- **Tactic**: king file semi
- **Comment**: [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e]
- **Tag Changes:**
  - Gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e
  - Lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e
  - Threats: king file semi, king file semi, file semi d, file semi e

### Branch 126: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 127: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 128: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 129: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 130: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 131: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 132: Qh5

- **Evaluation**: +0.19
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open h5-d1
- **Comment**: [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1]
- **Tag Changes:**
  - Gained: tag.diagonal.open.h5-d1
  - Lost: tag.diagonal.open.d1-h5
  - Threats: diagonal open h5-d1

### Branch 133: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 134: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 135: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 136: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 137: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 138: g6

- **Evaluation**: -0.08
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open f8-h6
- **Comment**: [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad]
- **Tag Changes:**
  - Gained: tag.diagonal.open.f8-h6, tag.bishop.bad
  - Threats: diagonal open f8-h6, bishop bad

### Branch 139: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 140: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 141: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 142: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 143: Qe2

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: diagonal open e2-h5
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6]
- **Tag Changes:**
  - Gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1
  - Threats: diagonal open e2-h5, diagonal open e2-a6

### Branch 144: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 145: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 146: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 147: Nxe5

- **Evaluation**: -0.05
- **Theme**: center_space,piece_activity
- **Tactic**: center control core
- **Comment**: [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3]
- **Tag Changes:**
  - Gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3
  - Lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad
  - Threats: center control core, center control core, key d5, diagonal open c8-h3

### Branch 148: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 149: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 150: Qxe4

- **Evaluation**: +0.31
- **Theme**: center_space,piece_activity
- **Tactic**: king file open
- **Comment**: [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6]
- **Tag Changes:**
  - Gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8
  - Lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6
  - Threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6

### Branch 151: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

### Branch 152: Bg7

- **Evaluation**: +0.21
- **Theme**: center_space,piece_activity
- **Tactic**: center control near
- **Comment**: [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near]
- **Tag Changes:**
  - Gained: tag.center.control.near
  - Lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3
  - Threats: center control near

### Branch 153: dxe5

- **Evaluation**: -0.02
- **Theme**: center_space,piece_activity
- **Tactic**: file open d
- **Comment**: [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6]
- **Tag Changes:**
  - Gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6
  - Lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight
  - Threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6

## Raw PGN

```pgn
[Event "Investigation"]
[Site "?"]
[Date "????.??.??"]
[Round "?"]
[White "?"]
[Black "?"]
[Result "*"]
[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]

{ [Starting tags: tag.king.attackers.count, tag.king.defenders.count, tag.king.attackers.count, tag.king.defenders.count, tag.activity.mobility.knight, tag.activity.mobility.bishop, tag.activity.mobility.rook, tag.activity.mobility.queen, tag.bishop.pair, tag.activity.mobility.knight, tag.activity.mobility.bishop, tag.activity.mobility.rook, tag.activity.mobility.queen, tag.bishop.pair] }
1. e4
{ [%eval +0.37] [%theme "center_space,pawn_structure"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.key.e4, tag.key.d5, tag.diagonal.open.f1-a6, tag.diagonal.open.d1-h5], [lost: none], [threats: center control near, key e4, key d5, diagonal open f1-a6, diagonal open d1-h5] }
( 1. e4
{ [%eval +0.30] [%theme "stopped_branch"] [%theme "d2_worse_than_original"] Branch stopped: d2_eval_below_original. D2 eval (+0.27) below original (+0.37, diff: -0.10). Final eval: +0.30. }
) 1... e5
{ [%eval +0.25] [%theme "center_space,pawn_structure"] [%tactic "key d4"] {[gained: tag.key.d4, tag.key.e5, tag.diagonal.open.f8-a3, tag.diagonal.open.d8-h4], [lost: none], [threats: key d4, key e5, diagonal open f8-a3, diagonal open d8-h4] }
2. Nf3
{ [%eval +0.36] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core], [lost: tag.key.d4, tag.diagonal.open.d1-h5], [threats: center control core] }
2... Nf6
{ [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.key.d5, tag.diagonal.open.d8-h4], [threats: none] }
3. d4
{ [%eval +0.34] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.key.d4, tag.diagonal.open.c1-h6, tag.lever.d5, tag.lever.e4], [lost: none], [threats: center control core, key d4, diagonal open c1-h6, lever d5, lever e4] }
3... Nxe4
{ [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.file.semi.e, tag.diagonal.open.d8-h4, tag.color.hole.light.d2, tag.piece.trapped], [lost: tag.center.control.near], [threats: king file semi, file semi e, diagonal open d8-h4, color hole light d2, piece trapped] }
4. Nxe5
{ [%eval +0.32] [%theme "center_space,pawn_structure"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.center.control.near, tag.file.open.e, tag.diagonal.open.d1-h5], [lost: tag.king.file.semi, tag.file.semi.e, tag.lever.d5, tag.lever.e4], [threats: king file open, king file open, center control near, file open e, diagonal open d1-h5] }
4... d5
{ [%eval +0.25] [%theme "center_space,piece_activity"] [%tactic "key d5"] {[gained: tag.key.d5, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [lost: none], [threats: key d5, diagonal open c8-h3, color hole dark d7] }
5. Nd2
{ [%eval +0.41] [%theme "center_space,piece_activity"] [%tactic "none"] {[gained: none], [lost: tag.center.control.core, tag.center.control.core, tag.diagonal.open.c1-h6, tag.color.hole.light.d2], [threats: none] }
5... Nd7
{ [%eval +0.38] [%theme "piece_activity,pawn_structure"] [%tactic "none"] {[gained: none], [lost: tag.center.control.near, tag.diagonal.open.c8-h3, tag.color.hole.dark.d7], [threats: none] }
6. Nxe4
{ [%eval +0.33] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near, tag.space.advantage, tag.diagonal.open.c1-h6], [lost: none], [threats: center control near, space advantage, diagonal open c1-h6] }
6... dxe4
{ [%eval +0.46] [%theme "center_space,piece_activity"] [%tactic "king file semi"] {[gained: tag.king.file.semi, tag.king.file.semi, tag.file.semi.d, tag.file.semi.e], [lost: tag.king.file.open, tag.king.file.open, tag.key.d5, tag.file.open.e], [threats: king file semi, king file semi, file semi d, file semi e] }
7. Qh5
{ [%eval +0.19] [%theme "center_space,piece_activity"] [%tactic "diagonal open h5-d1"] {[gained: tag.diagonal.open.h5-d1], [lost: tag.diagonal.open.d1-h5], [threats: diagonal open h5-d1] }
7... g6
{ [%eval -0.08] [%theme "center_space,piece_activity"] [%tactic "diagonal open f8-h6"] {[gained: tag.diagonal.open.f8-h6, tag.bishop.bad], [lost: none], [threats: diagonal open f8-h6, bishop bad] }
8. Qe2
{ [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "diagonal open e2-h5"] {[gained: tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [lost: tag.diagonal.open.f1-a6, tag.diagonal.open.h5-d1], [threats: diagonal open e2-h5, diagonal open e2-a6] }
8... Nxe5
{ [%eval -0.05] [%theme "center_space,piece_activity"] [%tactic "center control core"] {[gained: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.diagonal.open.c8-h3], [lost: tag.center.control.near, tag.space.advantage, tag.center.control.near, tag.piece.trapped, tag.bishop.bad], [threats: center control core, center control core, key d5, diagonal open c8-h3] }
9. Qxe4
{ [%eval +0.31] [%theme "center_space,piece_activity"] [%tactic "king file open"] {[gained: tag.king.file.open, tag.king.file.open, tag.file.open.e, tag.diagonal.open.f1-a6, tag.diagonal.open.e4-c6, tag.diagonal.open.long.h1a8], [lost: tag.center.control.core, tag.center.control.core, tag.key.d5, tag.file.semi.e, tag.diagonal.open.e2-h5, tag.diagonal.open.e2-a6], [threats: king file open, king file open, file open e, diagonal open f1-a6, diagonal open e4-c6] }
9... Bg7
{ [%eval +0.21] [%theme "center_space,piece_activity"] [%tactic "center control near"] {[gained: tag.center.control.near], [lost: tag.diagonal.open.f8-h6, tag.diagonal.open.f8-a3], [threats: center control near] }
10. dxe5
{ [%eval -0.02] [%theme "center_space,piece_activity"] [%tactic "file open d"] {[gained: tag.file.open.d, tag.file.semi.e, tag.color.hole.dark.d1, tag.color.hole.light.d2, tag.color.hole.light.f6], [lost: tag.key.d4, tag.file.semi.d, tag.file.open.e, tag.activity.mobility.knight], [threats: file open d, file semi e, color hole dark d1, color hole light d2, color hole light f6] }
*
```
