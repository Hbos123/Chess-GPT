/**
 * UI Command Handler
 * Maps LLM-emitted commands to frontend actions.
 */

export interface UICommand {
  action:
    | 'load_position'
    | 'new_tab'
    | 'navigate'
    | 'annotate'
    | 'push_move'
    | 'set_fen'
    | 'set_pgn'
    | 'delete_move'
    | 'delete_variation'
    | 'promote_variation'
    | 'set_ai_game';
  params: Record<string, any>;
}

export interface CommandContext {
  setFen: (fen: string) => void;
  setPgn: (pgn: string) => void;
  setAnnotations: (annotations: any) => void;
  navigate: (index?: number, offset?: number) => void;
  pushMove: (san: string) => void;
  deleteMove: (ply?: number) => void;
  deleteVariation: (ply?: number) => void;
  promoteVariation: (ply?: number) => void;
  newTab: (params: { type: string; fen?: string; pgn?: string; title?: string }) => void;
  setAiGame: (active: boolean, aiSide?: 'white' | 'black' | null, makeMoveNow?: boolean) => void;
}

export function handleUICommands(commands: UICommand[], context: CommandContext) {
  if (!commands || !Array.isArray(commands)) return;

  console.log(`🎮 [COMMAND_HANDLER] Processing ${commands.length} commands`);

  commands.forEach(cmd => {
    try {
      switch (cmd.action) {
        case 'load_position':
          if (cmd.params.fen) {
            context.setFen(cmd.params.fen);
          }
          break;

        case 'set_fen':
          if (cmd.params.fen) {
            context.setFen(cmd.params.fen);
          }
          break;

        case 'set_pgn':
          if (cmd.params.pgn) {
            context.setPgn(cmd.params.pgn);
          }
          break;

        case 'new_tab':
          context.newTab({
            type: cmd.params.type || 'review',
            fen: cmd.params.fen,
            pgn: cmd.params.pgn,
            title: cmd.params.title
          });
          break;

        case 'navigate':
          context.navigate(cmd.params.index, cmd.params.offset);
          break;

        case 'annotate':
          context.setAnnotations({
            arrows: cmd.params.arrows || [],
            highlights: cmd.params.squares || []
          });
          break;

        case 'push_move':
          if (cmd.params.san) {
            context.pushMove(cmd.params.san);
          }
          break;

        case 'delete_move':
          context.deleteMove(cmd.params.ply);
          break;

        case 'delete_variation':
          context.deleteVariation(cmd.params.ply);
          break;

        case 'promote_variation':
          context.promoteVariation(cmd.params.ply);
          break;

        case 'set_ai_game':
          context.setAiGame(
            cmd.params.active ?? true,
            cmd.params.ai_side || null,
            cmd.params.make_move_now ?? false
          );
          break;

        default:
          console.warn(`Unknown UI command action: ${cmd.action}`);
      }
    } catch (err) {
      console.error(`Error executing UI command ${cmd.action}:`, err);
    }
  });
}


