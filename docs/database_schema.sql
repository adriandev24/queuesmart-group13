PRAGMA foreign_keys = ON;

CREATE TABLE user_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user','administrator')),
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_user_credentials_email ON user_credentials(email);

CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES user_credentials(id) ON DELETE CASCADE,
    full_name VARCHAR(80) NOT NULL,
    contact_info VARCHAR(120),
    preferences VARCHAR(250)
);

CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(250) NOT NULL,
    expected_duration INTEGER NOT NULL CHECK (expected_duration BETWEEN 1 AND 120),
    priority_level VARCHAR(10) NOT NULL CHECK (priority_level IN ('low','medium','high')),
    created_at DATETIME NOT NULL
);

CREATE TABLE queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL UNIQUE REFERENCES services(id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_queues_service_id ON queues(service_id);

CREATE TABLE queue_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES user_credentials(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 1),
    join_time DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(10) NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting','served','canceled')),
    reason_for_visit VARCHAR(200) NOT NULL,
    UNIQUE(queue_id,user_id,join_time)
);
CREATE INDEX ix_queue_entries_queue_id ON queue_entries(queue_id);
CREATE INDEX ix_queue_entries_user_id ON queue_entries(user_id);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user_credentials(id) ON DELETE CASCADE,
    message VARCHAR(300) NOT NULL,
    timestamp DATETIME NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'sent' CHECK (status IN ('sent','viewed'))
);
CREATE INDEX ix_notifications_user_id ON notifications(user_id);

CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user_credentials(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    queue_entry_id INTEGER NOT NULL UNIQUE REFERENCES queue_entries(id) ON DELETE CASCADE,
    joined_at DATETIME NOT NULL,
    completed_at DATETIME NOT NULL,
    outcome VARCHAR(10) NOT NULL CHECK (outcome IN ('served','canceled')),
    wait_minutes INTEGER NOT NULL DEFAULT 0 CHECK (wait_minutes >= 0)
);
CREATE INDEX ix_history_user_id ON history(user_id);
CREATE INDEX ix_history_service_id ON history(service_id);

CREATE TABLE session_tokens (
    token VARCHAR(128) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_credentials(id) ON DELETE CASCADE,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_session_tokens_user_id ON session_tokens(user_id);
