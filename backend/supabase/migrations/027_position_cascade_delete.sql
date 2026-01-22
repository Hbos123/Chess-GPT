-- Migration 027: Position Cascade Delete
-- Changes positions.from_game_id foreign key to CASCADE delete
-- Ensures positions are automatically deleted when games are deleted/compressed

-- Drop existing foreign key constraint
ALTER TABLE public.positions 
DROP CONSTRAINT IF EXISTS positions_from_game_id_fkey;

-- Recreate with CASCADE delete
ALTER TABLE public.positions
ADD CONSTRAINT positions_from_game_id_fkey 
FOREIGN KEY (from_game_id) 
REFERENCES public.games(id) 
ON DELETE CASCADE;

-- Comment
COMMENT ON CONSTRAINT positions_from_game_id_fkey ON public.positions IS 
'Foreign key with CASCADE delete: positions are automatically deleted when games are deleted';


