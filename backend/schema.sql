PRAGMA foreign_keys = ON;

CREATE TABLE user_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME NOT NULL,
    CONSTRAINT ck_user_email_length CHECK (length(email) BETWEEN 3 AND 254),
    CONSTRAINT ck_user_role CHECK (role IN ('user', 'administrator'))
);
CREATE INDEX ix_user_credentials_email ON user_credentials(email);

CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    full_name VARCHAR(80) NOT NULL,
    contact_info VARCHAR(120),
    preferences VARCHAR(250),
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id)
        REFERENCES user_credentials(id) ON DELETE CASCADE,
    CONSTRAINT ck_profile_name_length CHECK (length(full_name) BETWEEN 2 AND 80),
    CONSTRAINT ck_profile_contact_length CHECK (contact_info IS NULL OR length(contact_info) <= 120),
    CONSTRAINT ck_profile_preferences_length CHECK (preferences IS NULL OR length(preferences) <= 250)
);

CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(250) NOT NULL,
    expected_duration INTEGER NOT NULL,
    priority_level VARCHAR(10) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT ck_service_name_length CHECK (length(name) BETWEEN 2 AND 100),
    CONSTRAINT ck_service_description_length CHECK (length(description) BETWEEN 5 AND 250),
    CONSTRAINT ck_service_duration CHECK (expected_duration BETWEEN 1 AND 120),
    CONSTRAINT ck_service_priority CHECK (priority_level IN ('low', 'medium', 'high'))
);

CREATE TABLE queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_queue_service FOREIGN KEY (service_id)
        REFERENCES services(id) ON DELETE CASCADE,
    CONSTRAINT ck_queue_status CHECK (status IN ('open', 'closed'))
);
CREATE INDEX ix_queues_service_id ON queues(service_id);

CREATE TABLE queue_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    join_time DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(10) NOT NULL DEFAULT 'waiting',
    reason_for_visit VARCHAR(200) NOT NULL,
    CONSTRAINT fk_entry_queue FOREIGN KEY (queue_id)
        REFERENCES queues(id) ON DELETE CASCADE,
    CONSTRAINT fk_entry_user FOREIGN KEY (user_id)
        REFERENCES user_credentials(id) ON DELETE CASCADE,
    CONSTRAINT ck_queue_entry_position CHECK (position >= 1),
    CONSTRAINT ck_queue_entry_status CHECK (status IN ('waiting', 'served', 'canceled')),
    CONSTRAINT ck_queue_entry_reason_length CHECK (length(reason_for_visit) BETWEEN 2 AND 200),
    CONSTRAINT uq_queue_entry_join UNIQUE (queue_id, user_id, join_time)
);
CREATE INDEX ix_queue_entries_queue_id ON queue_entries(queue_id);
CREATE INDEX ix_queue_entries_user_id ON queue_entries(user_id);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message VARCHAR(300) NOT NULL,
    timestamp DATETIME NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'sent',
    CONSTRAINT fk_notification_user FOREIGN KEY (user_id)
        REFERENCES user_credentials(id) ON DELETE CASCADE,
    CONSTRAINT ck_notification_message_length CHECK (length(message) BETWEEN 1 AND 300),
    CONSTRAINT ck_notification_status CHECK (status IN ('sent', 'viewed'))
);
CREATE INDEX ix_notifications_user_id ON notifications(user_id);

CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    queue_entry_id INTEGER NOT NULL UNIQUE,
    joined_at DATETIME NOT NULL,
    completed_at DATETIME NOT NULL,
    outcome VARCHAR(10) NOT NULL,
    wait_minutes INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_history_user FOREIGN KEY (user_id)
        REFERENCES user_credentials(id) ON DELETE CASCADE,
    CONSTRAINT fk_history_service FOREIGN KEY (service_id)
        REFERENCES services(id) ON DELETE RESTRICT,
    CONSTRAINT fk_history_entry FOREIGN KEY (queue_entry_id)
        REFERENCES queue_entries(id) ON DELETE CASCADE,
    CONSTRAINT ck_history_outcome CHECK (outcome IN ('served', 'canceled')),
    CONSTRAINT ck_history_wait_minutes CHECK (wait_minutes >= 0)
);
CREATE INDEX ix_history_user_id ON history(user_id);
CREATE INDEX ix_history_service_id ON history(service_id);

CREATE TABLE session_tokens (
    token VARCHAR(128) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id)
        REFERENCES user_credentials(id) ON DELETE CASCADE
);
CREATE INDEX ix_session_tokens_user_id ON session_tokens(user_id);
