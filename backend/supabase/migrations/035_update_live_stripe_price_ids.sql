-- ============================================================================
-- Update Live Stripe Price IDs
-- Updates subscription_tiers table with live mode Stripe Price IDs
-- ============================================================================

-- Update Lite tier with live Stripe Price ID
UPDATE public.subscription_tiers 
SET stripe_price_id = 'price_1Sufwh8XTZvE8cds1pfQZTp0'
WHERE id = 'lite';

-- Update Starter tier with live Stripe Price ID
UPDATE public.subscription_tiers 
SET stripe_price_id = 'price_1SufxF8XTZvE8cdsnqoGcOlM'
WHERE id = 'starter';

-- Update Full tier with live Stripe Price ID
UPDATE public.subscription_tiers 
SET stripe_price_id = 'price_1Sufxo8XTZvE8cdsywuJKKhd'
WHERE id = 'full';

-- Verify updates
SELECT id, name, stripe_price_id 
FROM public.subscription_tiers 
WHERE id IN ('lite', 'starter', 'full')
ORDER BY 
  CASE id 
    WHEN 'lite' THEN 1 
    WHEN 'starter' THEN 2 
    WHEN 'full' THEN 3 
  END;
