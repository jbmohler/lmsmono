create extension if not exists "uuid-ossp";

create schema databits;

CREATE TABLE databits.bits (
    id uuid primary key default uuid_generate_v1mc(),
    caption character varying(50),
    data text,
    website character varying(200),
    uname character varying(45),
    pword character varying(20)
);

CREATE TABLE databits.tags (
    id uuid primary key default uuid_generate_v1mc(),
    name character varying(100),
    description text
);

CREATE TABLE databits.tagbits (
    tag_id uuid NOT NULL references databits.tags(id),
    bit_id uuid NOT NULL references databits.bits(id),
    primary key (tag_id, bit_id)
);

create view databits.perfts_search as 
select id, 
    to_tsvector(coalesce(caption, ''))||
    to_tsvector(coalesce(data, ''))||
    to_tsvector(coalesce(website, '')) as fts_search
from databits.bits;
