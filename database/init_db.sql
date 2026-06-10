CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rescue_robots (
    id VARCHAR PRIMARY KEY,
    status VARCHAR DEFAULT 'IDLE',
    pos_x FLOAT,
    pos_y FLOAT
);

CREATE TABLE IF NOT EXISTS survivors (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    birth_year INTEGER,
    sex VARCHAR(10),
    phone_number VARCHAR(20),
    face_vector vector(256)
);

CREATE TABLE IF NOT EXISTS survivor_logs (
    log_number BIGSERIAL PRIMARY KEY,
    id VARCHAR(50) REFERENCES survivors(id),
    detected_x FLOAT NOT NULL,
    detected_y FLOAT NOT NULL,
    similarity FLOAT,
    robot_id VARCHAR(50) DEFAULT 'robot1',
    img_path VARCHAR(255),
    detection_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incident_logs (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    robot_id VARCHAR,
    message VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS login_data (
    username VARCHAR(20) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL
);

INSERT INTO login_data (username, password_hash)
VALUES ('fuoco1234', '$2b$12$wvrUTXBktstpuXruItn2B.DcYHj1tMpxHP3aDmsaoXQqU4qRhtfy2')
ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash;
