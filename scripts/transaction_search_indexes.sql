-- Indexes to make transaction search (app-transaction-list) fast without a
-- date horizon.
--
-- Before this, hacc.transactions had only its primary key, so every search
-- seq-scanned the full history and computed four to_tsvector() values per row.
--
-- transactions_fts_idx       - GIN on the payee/memo tsvector expression. Must
--                              match backend/api/transactions.py
--                              sql_select_transactions() exactly.
-- transactions_tranref_trgm_idx - trigram GIN so `tranref ILIKE '%q%'` is
--                              indexable; otherwise the OR forces a seq scan.
-- transactions_trandate_idx  - ORDER BY trandate DESC, tid DESC LIMIT n and
--                              date-range filters.
-- splits_account_stid_idx    - account filter (EXISTS on splits.account_id).
--
-- CONCURRENTLY avoids blocking writes but cannot run inside a transaction,
-- so this file must be run with psql in autocommit mode (the default; do NOT
-- use --single-transaction).
--
-- If a CONCURRENTLY build fails it leaves an INVALID index behind, which
-- IF NOT EXISTS will then skip. Check with:
--   SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
-- and DROP INDEX CONCURRENTLY the offender before re-running.

\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS transactions_fts_idx
    ON hacc.transactions USING gin ((
        to_tsvector('simple',  coalesce(payee, '')) ||
        to_tsvector('simple',  coalesce(memo,  '')) ||
        to_tsvector('english', coalesce(payee, '')) ||
        to_tsvector('english', coalesce(memo,  ''))
    ));

CREATE INDEX CONCURRENTLY IF NOT EXISTS transactions_tranref_trgm_idx
    ON hacc.transactions USING gin (tranref gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS transactions_trandate_idx
    ON hacc.transactions (trandate DESC, tid DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS splits_account_stid_idx
    ON hacc.splits (account_id, stid);

ANALYZE hacc.transactions;
ANALYZE hacc.splits;
