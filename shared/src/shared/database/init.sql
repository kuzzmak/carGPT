-- PostgreSQL initialization script for carGPT
-- This script creates the application database, user, and schema

-- Environment variables available:
-- CARGPT_DB_NAME (default: ads_db)
-- CARGPT_DB_USER (default: adsuser) 
-- CARGPT_DB_PASSWORD (default: pass)

-- Set default values if environment variables are not provided
\set db_name `echo "${CARGPT_DB_NAME:-ads_db}"`
\set db_user `echo "${CARGPT_DB_USER:-adsuser}"`
\set db_password `echo "${CARGPT_DB_PASSWORD:-pass}"`

-- Note: User and database are automatically created by PostgreSQL Docker container
-- using POSTGRES_USER, POSTGRES_DB, and POSTGRES_PASSWORD environment variables

-- Connect to the new database
\connect :db_name

-- Enable the citext extension for case-insensitive text operations
CREATE EXTENSION IF NOT EXISTS citext;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE :db_name TO :db_user;
GRANT ALL ON SCHEMA public TO :db_user;

-- Create the ads table with citext for case-insensitive text columns
CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    insertion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_created TIMESTAMP NOT NULL,
    ad_duration TIMESTAMP NOT NULL, 
    price NUMERIC(10, 2),
    location CITEXT,
    make CITEXT,
    model CITEXT,
    type CITEXT,
    chassis_number CITEXT,
    manufacture_year INT,
    model_year INT,
    mileage INT,
    engine CITEXT,
    power INT,
    displacement INT,
    transmission CITEXT,
    condition CITEXT,
    owner CITEXT,
    service_book BOOLEAN,
    garaged BOOLEAN,
    in_traffic_since INT,
    first_registration_in_croatia INT,
    registered_until VARCHAR(20),
    fuel_consumption VARCHAR(20),
    eco_category VARCHAR(20),
    number_of_gears VARCHAR(20),
    warranty VARCHAR(20),
    average_co2_emission VARCHAR(20),
    video_call_viewing BOOLEAN,
    gas BOOLEAN,
    auto_warranty VARCHAR(20),
    number_of_doors INT,
    chassis_type CITEXT,
    number_of_seats INT,
    drive_type CITEXT,
    color CITEXT,
    metalic_color BOOLEAN,
    suspension CITEXT,
    tire_size VARCHAR(20),
    internal_code VARCHAR(50)
);

-- Grant table permissions to the application user
GRANT ALL PRIVILEGES ON TABLE ads TO :db_user;
GRANT USAGE, SELECT ON SEQUENCE ads_id_seq TO :db_user;

-- Create indexes for common search fields
CREATE INDEX IF NOT EXISTS idx_ads_url ON ads(url);
CREATE INDEX IF NOT EXISTS idx_ads_make ON ads(make);
CREATE INDEX IF NOT EXISTS idx_ads_model ON ads(model);
CREATE INDEX IF NOT EXISTS idx_ads_location ON ads(location);
CREATE INDEX IF NOT EXISTS idx_ads_price ON ads(price);
CREATE INDEX IF NOT EXISTS idx_ads_manufacture_year ON ads(manufacture_year);
CREATE INDEX IF NOT EXISTS idx_ads_insertion_time ON ads(insertion_time);
CREATE INDEX IF NOT EXISTS idx_ads_make_model ON ads(make, model);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id UUID UNIQUE NOT NULL,
    user_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grant table permissions to the application user
GRANT ALL PRIVILEGES ON TABLE conversations TO :db_user;
GRANT USAGE, SELECT ON SEQUENCE conversations_id_seq TO :db_user;

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
