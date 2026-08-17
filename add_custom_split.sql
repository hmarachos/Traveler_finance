-- Add custom_split_weights column to expenses table to support manual split distribution
-- This will store JSON object with family_id as keys and weights as values
-- Example: {"1": 2, "2": 1} means family 1 gets 2 parts, family 2 gets 1 part

ALTER TABLE expenses ADD COLUMN custom_split_weights TEXT;
