-- Development seed data for accounting system
-- Run manually: docker-compose exec postgres psql -U lms -d lms -f /docker-entrypoint-initdb.d/sql/seed_dev_data.sql

-- ============================================================================
-- Account Types (the 5 standard types)
-- ============================================================================
-- debit=true means debits increase the account
-- balance_sheet=true means it appears on balance sheet (vs income statement)

INSERT INTO hacc.accounttypes (atype_name, description, balance_sheet, debit, retained_earnings, sort) VALUES
  ('Asset',     'Resources owned by the business',                    true,  true,  false, 1),
  ('Liability', 'Obligations owed to others',                         true,  false, false, 2),
  ('Equity',    'Owner''s residual interest in assets',               true,  false, false, 3),
  ('Income',    'Revenue from business operations',                   false, false, false, 4),
  ('Expense',   'Costs incurred in business operations',              false, true,  false, 5);

-- ============================================================================
-- Journals
-- ============================================================================

INSERT INTO hacc.journals (jrn_name, description) VALUES
  ('General',     'General ledger journal for day-to-day transactions'),
  ('Investments', 'Investment portfolio transactions');

-- ============================================================================
-- Accounts (using CTEs to reference types and journals by name)
-- ============================================================================

WITH types AS (
  SELECT id, atype_name FROM hacc.accounttypes
),
journals AS (
  SELECT id, jrn_name FROM hacc.journals
)
INSERT INTO hacc.accounts (type_id, journal_id, acc_name, description)
SELECT t.id, j.id, acc.acc_name, acc.description
FROM (VALUES
  -- Asset accounts (General journal)
  ('Asset', 'General', 'Checking', 'Primary business checking account'),
  ('Asset', 'General', 'Savings', 'Business savings account'),
  ('Asset', 'General', 'Petty Cash', 'Cash on hand for small expenses'),
  ('Asset', 'General', 'Accounts Recv', 'Money owed by customers'),

  -- Asset accounts (Investments journal)
  ('Asset', 'Investments', 'Brokerage', 'Main investment brokerage account'),
  ('Asset', 'Investments', 'Retirement', '401k retirement account'),

  -- Liability accounts
  ('Liability', 'General', 'Accounts Pay', 'Money owed to vendors'),
  ('Liability', 'General', 'Credit Card', 'Business credit card balance'),
  ('Liability', 'General', 'Loan Payable', 'Outstanding business loan'),

  -- Equity accounts
  ('Equity', 'General', 'Owner Capital', 'Owner''s contributed capital'),
  ('Equity', 'General', 'Retained Earn', 'Accumulated profits retained in business'),
  ('Equity', 'General', 'Distributions', 'Owner withdrawals and distributions'),

  -- Income accounts
  ('Income', 'General', 'Sales Revenue', 'Revenue from product sales'),
  ('Income', 'General', 'Service Income', 'Revenue from services rendered'),
  ('Income', 'General', 'Interest Inc', 'Interest earned on deposits'),
  ('Income', 'Investments', 'Dividend Inc', 'Dividend income from investments'),
  ('Income', 'Investments', 'Capital Gains', 'Realized gains on investments'),

  -- Expense accounts
  ('Expense', 'General', 'Rent Expense', 'Office and facility rent'),
  ('Expense', 'General', 'Utilities', 'Electric, water, internet, phone'),
  ('Expense', 'General', 'Office Supply', 'Office supplies and materials'),
  ('Expense', 'General', 'Payroll', 'Employee wages and salaries'),
  ('Expense', 'General', 'Insurance', 'Business insurance premiums'),
  ('Expense', 'General', 'Bank Fees', 'Bank service charges and fees'),
  ('Expense', 'Investments', 'Trading Fees', 'Brokerage commissions and fees')
) AS acc(type_name, journal_name, acc_name, description)
JOIN types t ON t.atype_name = acc.type_name
JOIN journals j ON j.jrn_name = acc.journal_name;

-- Mark Retained Earnings as the retained earnings account
UPDATE hacc.accounttypes
SET retained_earnings = true
WHERE atype_name = 'Equity';

-- ============================================================================
-- Sample Transactions
-- ============================================================================
-- Each transaction must balance: sum of all splits = 0
-- Positive sum = debit, Negative sum = credit
--
-- Dates float relative to the day this script runs, so the data is always
-- recent instead of drifting further into the past with every fresh dev
-- database. The base date is the Monday on/before (today - 80 days); every
-- transaction is that base plus a fixed day-offset chosen to land on a
-- weekday, so the whole set runs Monday-to-Thursday from ~80 days ago up to
-- near the present.

-- Helper function to get account ID by name (for readability)
CREATE OR REPLACE FUNCTION hacc.get_account_id(p_name varchar) RETURNS uuid AS $$
  SELECT id FROM hacc.accounts WHERE acc_name = p_name LIMIT 1;
$$ LANGUAGE sql;

-- Helper function for the floating base date (a Monday, ~80 days back)
CREATE OR REPLACE FUNCTION hacc.seed_base_date() RETURNS date AS $$
  SELECT date_trunc('week', CURRENT_DATE - INTERVAL '80 days')::date;
$$ LANGUAGE sql;

-- Transaction 1: Owner invests capital (day 0, Mon)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date(), 'OPEN-001', 'Owner', 'Initial capital investment')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Checking'), 50000.00),      -- Debit: increase asset
  (hacc.get_account_id('Owner Capital'), -50000.00) -- Credit: increase equity
) AS splits(acc_id, amount);

-- Transaction 2: Pay rent (day 4, Fri)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 4, 'CHK-001', 'Acme Properties', 'Office rent')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Rent Expense'), 2500.00),  -- Debit: increase expense
  (hacc.get_account_id('Checking'), -2500.00)      -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 3: Receive payment from customer (day 9, Wed)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 9, 'DEP-001', 'ABC Corporation', 'Payment for consulting services')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Checking'), 5000.00),       -- Debit: increase asset
  (hacc.get_account_id('Service Income'), -5000.00) -- Credit: increase income
) AS splits(acc_id, amount);

-- Transaction 4: Purchase office supplies on credit card (day 11, Fri)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 11, 'CC-001', 'Office Depot', 'Printer paper and toner')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Office Supply'), 150.00),  -- Debit: increase expense
  (hacc.get_account_id('Credit Card'), -150.00)    -- Credit: increase liability
) AS splits(acc_id, amount);

-- Transaction 5: Pay credit card bill (day 14, Mon)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 14, 'CHK-002', 'Visa', 'Credit card payment')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Credit Card'), 150.00),   -- Debit: decrease liability
  (hacc.get_account_id('Checking'), -150.00)      -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 6: Transfer to savings (day 21, Mon)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 21, 'TFR-001', 'Internal', 'Monthly savings transfer')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Savings'), 5000.00),   -- Debit: increase asset
  (hacc.get_account_id('Checking'), -5000.00)  -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 7: Invest in brokerage (Investments journal) (day 24, Thu)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 24, 'INV-001', 'Fidelity', 'Initial investment deposit')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Brokerage'), 10000.00),  -- Debit: increase asset
  (hacc.get_account_id('Checking'), -10000.00)   -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 8: Receive dividend (day 30, Wed)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 30, 'DIV-001', 'Vanguard ETF', 'Quarterly dividend distribution')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Brokerage'), 125.50),     -- Debit: increase asset
  (hacc.get_account_id('Dividend Inc'), -125.50)  -- Credit: increase income
) AS splits(acc_id, amount);

-- Transaction 9: Pay utilities (day 35, Mon)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 35, 'CHK-003', 'City Utilities', 'Monthly utilities')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Utilities'), 285.00),   -- Debit: increase expense
  (hacc.get_account_id('Checking'), -285.00)    -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 10: Complex transaction - sale with multiple income sources (day 39, Fri)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 39, 'INV-002', 'XYZ Client', 'Product sale with installation service')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Accounts Recv'), 3500.00),  -- Debit: increase asset
  (hacc.get_account_id('Sales Revenue'), -2500.00), -- Credit: product revenue
  (hacc.get_account_id('Service Income'), -1000.00) -- Credit: installation service
) AS splits(acc_id, amount);

-- Transaction 11: Receive partial payment on invoice (day 44, Wed)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 44, 'DEP-002', 'XYZ Client', 'Partial payment on invoice')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Checking'), 2000.00),       -- Debit: increase cash
  (hacc.get_account_id('Accounts Recv'), -2000.00)  -- Credit: decrease receivable
) AS splits(acc_id, amount);

-- Transaction 12: Bank interest earned (day 60, Fri)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 60, 'INT-001', 'First National Bank', 'Monthly interest')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Savings'), 12.50),       -- Debit: increase asset
  (hacc.get_account_id('Interest Inc'), -12.50)  -- Credit: increase income
) AS splits(acc_id, amount);

-- Transaction 13: Pay insurance (annual premium) (day 63, Mon)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 63, 'CHK-004', 'State Farm', 'Annual business insurance')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Insurance'), 1800.00),   -- Debit: increase expense
  (hacc.get_account_id('Checking'), -1800.00)    -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 14: Owner distribution (day 74, Fri)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 74, 'CHK-005', 'Owner', 'Owner distribution')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Distributions'), 3000.00), -- Debit: decrease equity
  (hacc.get_account_id('Checking'), -3000.00)      -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Transaction 15: Bank fee (day 80, Thu — near the present)
WITH txn AS (
  INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
  VALUES (hacc.seed_base_date() + 80, 'FEE-001', 'First National Bank', 'Monthly service charge')
  RETURNING tid
)
INSERT INTO hacc.splits (stid, account_id, sum)
SELECT txn.tid, acc_id, amount FROM txn,
(VALUES
  (hacc.get_account_id('Bank Fees'), 15.00),    -- Debit: increase expense
  (hacc.get_account_id('Checking'), -15.00)     -- Credit: decrease asset
) AS splits(acc_id, amount);

-- Clean up helper functions
DROP FUNCTION hacc.get_account_id(varchar);
DROP FUNCTION hacc.seed_base_date();

-- ============================================================================
-- Reconciliation Tags
-- ============================================================================

INSERT INTO hacc.tags (tag_name, description) VALUES
  ('Bank Pending',    'Draft reconciliation — matched on statement but not yet finalized'),
  ('Bank Reconciled', 'Fully reconciled against a bank or credit card statement');

-- ============================================================================
-- Verification queries (optional - run to confirm data integrity)
-- ============================================================================

-- Check that all transactions balance
-- SELECT t.tid, t.trandate, t.payee, SUM(s.sum) as balance
-- FROM hacc.transactions t
-- JOIN hacc.splits s ON s.stid = t.tid
-- GROUP BY t.tid, t.trandate, t.payee
-- HAVING SUM(s.sum) != 0;

-- Account balances summary
-- SELECT
--   at.atype_name,
--   a.acc_name,
--   SUM(s.sum) as balance
-- FROM hacc.accounts a
-- JOIN hacc.accounttypes at ON at.id = a.type_id
-- LEFT JOIN hacc.splits s ON s.account_id = a.id
-- GROUP BY at.atype_name, a.acc_name, at.sort
-- ORDER BY at.sort, a.acc_name;
