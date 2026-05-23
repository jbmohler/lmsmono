-- Improve full-text search by combining 'simple' and 'english' tsvector configs.
--
-- 'english' provides stemming (searching → search) but strips stop words ("of",
-- "and", "the") and mangles proper nouns.
-- 'simple' lowercases only — preserves stop words and proper noun tokens exactly.
-- Together they give better recall for company names, personal names, and memos.
--
-- The backend query also adds a prefix branch using to_tsquery('simple', 'word:*')
-- so that partial typing ("Smi" matches "Smith") works at search-as-you-type speed.
--
-- Covers: contacts.perfts_search, contacts.personas_calc, contacts.bits,
--         databits.perfts_search

CREATE OR REPLACE VIEW contacts.perfts_search AS
SELECT id,
    to_tsvector('simple', coalesce(l_name, ''))||
    to_tsvector('simple', coalesce(f_name, ''))||
    to_tsvector('simple', coalesce(organization, ''))||
    to_tsvector('simple', coalesce(title, ''))||
    to_tsvector('simple', coalesce(memo, ''))||
    to_tsvector('english', coalesce(l_name, ''))||
    to_tsvector('english', coalesce(f_name, ''))||
    to_tsvector('english', coalesce(organization, ''))||
    to_tsvector('english', coalesce(title, ''))||
    to_tsvector('english', coalesce(memo, '')) AS fts_search
FROM contacts.personas;

CREATE OR REPLACE VIEW contacts.personas_calc AS
SELECT personas.*,
    to_tsvector('simple', coalesce(l_name, ''))||
    to_tsvector('simple', coalesce(f_name, ''))||
    to_tsvector('simple', coalesce(organization, ''))||
    to_tsvector('simple', coalesce(title, ''))||
    to_tsvector('simple', coalesce(memo, ''))||
    to_tsvector('english', coalesce(l_name, ''))||
    to_tsvector('english', coalesce(f_name, ''))||
    to_tsvector('english', coalesce(organization, ''))||
    to_tsvector('english', coalesce(title, ''))||
    to_tsvector('english', coalesce(memo, '')) AS fts_search,
    concat_ws(' ',
        CASE WHEN personas.title = '' THEN NULL ELSE personas.title END,
        CASE WHEN personas.f_name = '' THEN NULL ELSE personas.f_name END,
        CASE WHEN personas.l_name = '' THEN NULL ELSE personas.l_name END) AS entity_name
FROM contacts.personas;

-- databits.perfts_search: upgrade from default (english-only) tsvector to
-- dual simple+english, matching the 3-branch backend search pattern.
CREATE OR REPLACE VIEW databits.perfts_search AS
SELECT id,
    to_tsvector('simple',  coalesce(caption, ''))||
    to_tsvector('simple',  coalesce(data, ''))||
    to_tsvector('simple',  coalesce(website, ''))||
    to_tsvector('english', coalesce(caption, ''))||
    to_tsvector('english', coalesce(data, ''))||
    to_tsvector('english', coalesce(website, '')) AS fts_search
FROM databits.bits;

CREATE OR REPLACE VIEW contacts.bits AS
(
    SELECT id, persona_id, 'urls' AS bit_type,
        name, memo, is_primary,
        bit_sequence,
        to_tsvector('simple', coalesce(memo, ''))||
        to_tsvector('simple', coalesce(name, ''))||
        to_tsvector('simple', coalesce(url, ''))||
        to_tsvector('english', coalesce(memo, ''))||
        to_tsvector('english', coalesce(name, ''))||
        to_tsvector('english', coalesce(url, '')) AS fts_search,
        json_build_object(
                'url', url,
                'username', username,
                'password_enc', password_enc,
                'pw_reset_dt', pw_reset_dt,
                'pw_next_reset_dt', pw_next_reset_dt) AS bit_data
    FROM contacts.urls
) UNION ALL (
    SELECT id, persona_id, 'street_addresses' AS bit_type,
        name, memo, is_primary,
        bit_sequence,
        to_tsvector('simple', coalesce(memo, ''))||
        to_tsvector('simple', coalesce(name, ''))||
        to_tsvector('simple', coalesce(address1, ''))||
        to_tsvector('simple', coalesce(address2, ''))||
        to_tsvector('simple', coalesce(city, ''))||
        to_tsvector('english', coalesce(memo, ''))||
        to_tsvector('english', coalesce(name, ''))||
        to_tsvector('english', coalesce(address1, ''))||
        to_tsvector('english', coalesce(address2, ''))||
        to_tsvector('english', coalesce(city, '')) AS fts_search,
        json_build_object(
                'address1', address1,
                'address2', address2,
                'city', city,
                'state', state,
                'zip', zip,
                'country', country) AS bit_data
    FROM contacts.street_addresses
) UNION ALL (
    SELECT id, persona_id, 'phone_numbers' AS bit_type,
        name, memo, is_primary,
        bit_sequence,
        to_tsvector('simple', coalesce(memo, ''))||
        to_tsvector('simple', coalesce(name, ''))||
        to_tsvector('english', coalesce(memo, ''))||
        to_tsvector('english', coalesce(name, '')) AS fts_search,
        json_build_object(
                'number', number) AS bit_data
    FROM contacts.phone_numbers
) UNION ALL (
    SELECT id, persona_id, 'email_addresses' AS bit_type,
        name, memo, is_primary,
        bit_sequence,
        to_tsvector('simple', coalesce(memo, ''))||
        to_tsvector('simple', coalesce(name, ''))||
        to_tsvector('english', coalesce(memo, ''))||
        to_tsvector('english', coalesce(name, '')) AS fts_search,
        json_build_object(
                'email', email) AS bit_data
    FROM contacts.email_addresses
);
