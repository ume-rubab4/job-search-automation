create table if not exists jobs (
  id            bigserial primary key,
  hash          text unique not null,
  source        text not null,          -- adzuna | jooble | arbeitnow | remotive
  platform      text,                   -- greenhouse | lever | ashby | workable | other
  title         text not null,
  company       text,
  country       text,                   -- ISO-2
  city          text,
  remote        boolean default false,
  url           text not null,
  description   text,
  salary        text,
  posted_at     timestamptz,
  found_at      timestamptz default now(),

  -- LLM analysis
  fit_score       int,
  matched_reqs    jsonb,
  missing_reqs    jsonb,
  visa_status     text,                 -- stated_yes | stated_no | not_mentioned | known_sponsor
  visa_evidence   text,
  company_size    text,                 -- large | medium | small | unknown
  needs_cover_letter boolean default false,
  role_family     text,

  status        text default 'found',   -- found | rejected | shortlisted | emailed | approved | skipped | applied | apply_failed | package_ready
  digest_no     int,                    -- number shown in the approval email
  digest_date   date,
  cv_path       text,
  cover_letter_path text,
  applied_at    timestamptz,
  apply_notes   text
);

create index if not exists jobs_status_idx on jobs(status);
create index if not exists jobs_digest_idx on jobs(digest_date, digest_no);

create table if not exists runs (
  id          bigserial primary key,
  ran_at      timestamptz default now(),
  found       int, shortlisted int, emailed int, applied int,
  notes       text
);
