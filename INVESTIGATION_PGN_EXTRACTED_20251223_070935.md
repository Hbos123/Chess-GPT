# Investigation PGN Documentation

*Generated: 2025-12-23 07:09:35*

## Main Line (Principal Variation)

*No moves in main line.*

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
