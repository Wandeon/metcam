-- FootballVision Pro Database Schema
-- Complete schema for activity logging, upload tracking, and system management

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'operator',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- Matches table
CREATE TABLE IF NOT EXISTS matches (
    id VARCHAR(100) PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    metadata TEXT  -- JSON: team names, scores, etc.
);

-- Recording sessions
CREATE TABLE IF NOT EXISTS recording_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id VARCHAR(100) NOT NULL,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    stopped_at DATETIME,
    duration_seconds INTEGER,
    cam0_file VARCHAR(500),
    cam1_file VARCHAR(500),
    cam0_size_bytes INTEGER,
    cam1_size_bytes INTEGER,
    frames_captured INTEGER DEFAULT 0,
    frames_dropped INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'recording',
    error_message TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

-- System events (Activity logging)
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type VARCHAR(50) NOT NULL,
    component VARCHAR(50),
    severity VARCHAR(20) DEFAULT 'info',
    user_id INTEGER,
    match_id VARCHAR(100),
    details TEXT,  -- JSON
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE INDEX IF NOT EXISTS idx_system_events_timestamp ON system_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_system_events_match ON system_events(match_id);

-- Cloud uploads tracking
CREATE TABLE IF NOT EXISTS cloud_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id VARCHAR(100) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    destination VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress_percent REAL DEFAULT 0,
    bytes_uploaded INTEGER DEFAULT 0,
    total_bytes INTEGER,
    bandwidth_limit_mbps INTEGER DEFAULT 10,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error_message TEXT,
    resume_position INTEGER DEFAULT 0,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE INDEX IF NOT EXISTS idx_cloud_uploads_match ON cloud_uploads(match_id);
CREATE INDEX IF NOT EXISTS idx_cloud_uploads_status ON cloud_uploads(status);

-- Processing jobs
CREATE TABLE IF NOT EXISTS processing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(100) UNIQUE NOT NULL,
    match_id VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL,  -- 'sidebyside', 'panoramic'
    status VARCHAR(20) DEFAULT 'pending',
    progress_percent REAL DEFAULT 0,
    current_step VARCHAR(100),
    output_path VARCHAR(500),
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error_message TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_match ON processing_jobs(match_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    read BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Device configuration
CREATE TABLE IF NOT EXISTS device_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration
INSERT OR IGNORE INTO device_config (key, value) VALUES
    ('device_name', 'FootballVision-01'),
    ('default_resolution', '1920x1080'),
    ('default_fps', '30'),
    ('default_bitrate', '4000'),
    ('upload_bandwidth_limit', '10'),
    ('auto_upload_enabled', 'true');

-- Insert default admin user (password: admin)
-- Password hash for 'admin' using bcrypt
INSERT OR IGNORE INTO users (email, password_hash, role) VALUES
    ('admin@localhost', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqgOjKdL1u', 'admin');
