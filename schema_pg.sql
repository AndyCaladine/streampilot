-- =============================================================
-- schema_pg.sql — StreamPilot PostgreSQL schema (production)
--
-- For live schema changes use the migrations/ folder.
--
-- Design rules:
--   Serial primary keys throughout
--   All channels share one database, isolated by channel_id
--   Soft delete (deleted_at) where data should be recoverable
--   Hard delete where rows are truly disposable
--   Platform-agnostic — built for Twitch now, YouTube and
--   TikTok later without schema changes
-- =============================================================


-- =============================================================
-- STREAMER SIDE
-- =============================================================

-- -------------------------------------------------------------
-- Users
-- One row per StreamPilot account.
-- No platform-specific columns here — platform identity lives
-- in user_platforms so one account can connect multiple platforms.
-- Created automatically on first login via any platform OAuth.
--
-- tier:              free | premium | lifer
-- status:            active | suspended
-- next_payment_due:  NULL for free and lifer tiers
-- beta_code_used:    code redeemed at registration, if any
-- -------------------------------------------------------------
CREATE TABLE users (
    id                SERIAL PRIMARY KEY,
    email             TEXT    UNIQUE,
    full_name         TEXT,
    chosen_name       TEXT,
    display_name      TEXT    NOT NULL,
    avatar_url        TEXT,
    tier              TEXT    NOT NULL DEFAULT 'free',
    status            TEXT    NOT NULL DEFAULT 'active',
    next_payment_due  TIMESTAMPTZ,
    beta_code_used    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at     TIMESTAMPTZ
);

CREATE TABLE user_platforms (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    platform              TEXT    NOT NULL,
    platform_user_id      TEXT    NOT NULL,
    platform_login        TEXT    NOT NULL,
    platform_display_name TEXT    NOT NULL,
    platform_avatar_url   TEXT,
    access_token          TEXT,
    refresh_token         TEXT,
    token_expiry          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at         TIMESTAMPTZ,
    UNIQUE(platform, platform_user_id)
);

CREATE TABLE channels (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    platform            TEXT    NOT NULL DEFAULT 'twitch',
    platform_channel_id TEXT    NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, platform_channel_id)
);

CREATE TABLE team_members (
    id          SERIAL PRIMARY KEY,
    channel_id  INTEGER NOT NULL REFERENCES channels(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT    NOT NULL DEFAULT 'mod',
    invited_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMPTZ,
    UNIQUE(channel_id, user_id)
);

CREATE TABLE invite_tokens (
    id              SERIAL PRIMARY KEY,
    channel_id      INTEGER NOT NULL REFERENCES channels(id),
    token           TEXT    NOT NULL UNIQUE,
    role            TEXT    NOT NULL DEFAULT 'mod',
    email           TEXT,
    twitch_user_id  TEXT,
    twitch_login    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ
);

CREATE TABLE beta_codes (
    id          SERIAL PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE,
    note        TEXT,
    created_by  INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMPTZ,
    used_at     TIMESTAMPTZ,
    used_by     INTEGER REFERENCES users(id)
);

CREATE TABLE overlay_tokens (
    id           SERIAL PRIMARY KEY,
    channel_id   INTEGER NOT NULL REFERENCES channels(id),
    overlay_type TEXT    NOT NULL,
    token        TEXT    NOT NULL UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, overlay_type)
);

CREATE TABLE IF NOT EXISTS commands (
    id          SERIAL PRIMARY KEY,
    channel_id  INTEGER NOT NULL REFERENCES channels(id),
    trigger     TEXT    NOT NULL,
    response    TEXT    NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    mod_only    INTEGER NOT NULL DEFAULT 0,
    cooldown_s  INTEGER NOT NULL DEFAULT 30,
    use_count   INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    UNIQUE(channel_id, trigger)

CREATE TABLE alert_configs (
    id            SERIAL PRIMARY KEY,
    channel_id    INTEGER NOT NULL REFERENCES channels(id),
    alert_type    TEXT    NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    message_text  TEXT,
    duration_ms   INTEGER NOT NULL DEFAULT 5000,
    sound_enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(channel_id, alert_type)
);

CREATE TABLE panels (
    id              SERIAL PRIMARY KEY,
    channel_id      INTEGER NOT NULL REFERENCES channels(id),
    name            TEXT    NOT NULL,
    content_type    TEXT    NOT NULL DEFAULT 'static',
    content_data    TEXT,
    schedule_mode   TEXT    NOT NULL DEFAULT 'interval',
    interval_mins   INTEGER,
    fixed_minute    INTEGER,
    duration_ms     INTEGER NOT NULL DEFAULT 8000,
    entry_animation TEXT    NOT NULL DEFAULT 'fade',
    exit_animation  TEXT    NOT NULL DEFAULT 'fade',
    anim_speed      TEXT    NOT NULL DEFAULT 'normal',
    enabled         INTEGER NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE event_log (
    id          SERIAL PRIMARY KEY,
    channel_id  INTEGER NOT NULL REFERENCES channels(id),
    event_type  TEXT    NOT NULL,
    event_data  TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE viewer_stats (
    id            SERIAL PRIMARY KEY,
    channel_id    INTEGER NOT NULL REFERENCES channels(id),
    viewer_count  INTEGER NOT NULL DEFAULT 0,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =============================================================
-- ADMIN SIDE
-- Completely separate from streamer tables.
-- No platform integration. Username and password only.
-- =============================================================

CREATE TABLE admin_users (
    id                   SERIAL PRIMARY KEY,
    username             TEXT    NOT NULL UNIQUE,
    email                TEXT    NOT NULL UNIQUE,
    password_hash        TEXT    NOT NULL,
    role                 TEXT    NOT NULL DEFAULT 'worker',
    password_changed_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    password_expires_at  TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '45 days'),
    must_change_password INTEGER NOT NULL DEFAULT 0,
    last_login_at        TIMESTAMPTZ,
    created_by           INTEGER REFERENCES admin_users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active               INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE admin_password_history (
    id             SERIAL PRIMARY KEY,
    admin_user_id  INTEGER NOT NULL REFERENCES admin_users(id),
    password_hash  TEXT    NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE beta_requests (
    id                SERIAL PRIMARY KEY,
    name              TEXT    NOT NULL,
    email             TEXT    NOT NULL UNIQUE,
    twitch_login      TEXT,
    reason            TEXT,
    status            TEXT    NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at       TIMESTAMPTZ,
    reviewed_by       INTEGER REFERENCES admin_users(id),
    streamer_tag      TEXT,
    platform          TEXT,
    consent_data      INTEGER NOT NULL DEFAULT 0,
    consent_marketing INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE overlay_connections (
    id                SERIAL PRIMARY KEY,
    channel_id        INTEGER NOT NULL REFERENCES channels(id),
    overlay_type      TEXT    NOT NULL,
    last_connected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, overlay_type)
);

CREATE TABLE user_preferences (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    preference TEXT    NOT NULL,
    value      TEXT    NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, preference)
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_profiles (
    id              SERIAL PRIMARY KEY,
    channel_id      INTEGER NOT NULL REFERENCES channels(id),
    twitch_user_id  TEXT    NOT NULL,
    twitch_login    TEXT    NOT NULL,
    nickname        TEXT,
    notes           TEXT,
    flag            TEXT    NOT NULL DEFAULT 'none',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, twitch_user_id)
);