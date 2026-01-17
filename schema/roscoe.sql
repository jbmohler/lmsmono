
create table public.roscoelogs (
    id serial primary key,
    msgtime timestamptz,
    rawtext text,
    fromphone character varying(20),
    processed boolean default false not null,
    media bytea
);
