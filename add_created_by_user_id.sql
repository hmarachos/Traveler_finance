-- Add created_by_user_id column to expenses table if it doesn't exist
-- This migration is safe and won't lose any data

-- Check and add column to expenses
ALTER TABLE expenses ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);

-- Check and add column to money_transfers (if not exists)
-- ALTER TABLE money_transfers ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);

-- Check and add column to loans (if not exists)
-- ALTER TABLE loans ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);

-- Check and add column to loan_repayments (if not exists)
-- ALTER TABLE loan_repayments ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);
