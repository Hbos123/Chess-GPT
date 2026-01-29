-- Add linked_accounts and related columns to profiles table
-- Run this in Supabase SQL Editor

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS linked_accounts jsonb DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS time_controls text[] DEFAULT ARRAY[]::text[],
ADD COLUMN IF NOT EXISTS profile_setup_complete boolean DEFAULT false;

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS profiles_linked_accounts_idx ON public.profiles USING gin (linked_accounts);

-- Add comments
COMMENT ON COLUMN public.profiles.linked_accounts IS 'Array of linked chess accounts: [{"platform": "chess.com", "username": "..."}, ...]';
COMMENT ON COLUMN public.profiles.time_controls IS 'Array of time controls user wants to analyze: ["bullet", "blitz", ...]';
COMMENT ON COLUMN public.profiles.profile_setup_complete IS 'Whether user has completed profile setup with linked accounts';
