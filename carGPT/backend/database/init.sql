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

-- Create user if not exists
CREATE USER :db_user WITH LOGIN PASSWORD :'db_password';

-- Create database if not exists
CREATE DATABASE :db_name OWNER :db_user;

-- Connect to the new database
\connect :db_name

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE :db_name TO :db_user;
GRANT ALL ON SCHEMA public TO :db_user;

-- Create the ads table
CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_created TIMESTAMP NOT NULL,
    price NUMERIC(10, 2),
    location VARCHAR(100),
    make VARCHAR(30),
    model VARCHAR(50),
    type VARCHAR(100),
    chassis_number VARCHAR(17),
    manufacture_year INT,
    model_year INT,
    mileage INT,
    engine VARCHAR(20),
    power INT,
    displacement INT,
    transmission VARCHAR(30),
    condition VARCHAR(20),
    owner VARCHAR(20),
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
    chassis_type VARCHAR(20),
    number_of_seats INT,
    drive_type VARCHAR(20),
    color VARCHAR(20),
    metalic_color BOOLEAN,
    suspension VARCHAR(20),
    tire_size VARCHAR(20)
);

-- Grant table permissions to the application user
GRANT ALL PRIVILEGES ON TABLE ads TO :db_user;
GRANT USAGE, SELECT ON SEQUENCE ads_id_seq TO :db_user;

-- Create indexes for common search fields
CREATE INDEX IF NOT EXISTS idx_ads_make ON ads(make);
CREATE INDEX IF NOT EXISTS idx_ads_model ON ads(model);
CREATE INDEX IF NOT EXISTS idx_ads_location ON ads(location);
CREATE INDEX IF NOT EXISTS idx_ads_price ON ads(price);
CREATE INDEX IF NOT EXISTS idx_ads_manufacture_year ON ads(manufacture_year);
CREATE INDEX IF NOT EXISTS idx_ads_insertion_time ON ads(insertion_time);
CREATE INDEX IF NOT EXISTS idx_ads_make_model ON ads(make, model);

COMMENT ON TABLE ads IS 'Table for storing car advertisement data';
COMMENT ON COLUMN ads.insertion_time IS 'Timestamp when the ad was inserted into the database';
COMMENT ON COLUMN ads.date_created IS 'Original creation date of the advertisement';
COMMENT ON COLUMN ads.chassis_number IS 'Vehicle Identification Number (VIN)';
COMMENT ON COLUMN ads.metalic_color IS 'Boolean indicating if the car has metallic paint';
