-- 015_default_currency.sql
-- Adds per-user default currency preference to profiles.

ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS default_currency char(3) NOT NULL DEFAULT 'SAR';
