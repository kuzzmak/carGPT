import sqlite3


connection = sqlite3.connect("ads.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE ads (
    id INTEGER PRIMARY KEY,
    location TEXT,
    make TEXT,
    model TEXT,
    type TEXT,
    chassis_number TEXT,
    manufacture_year TEXT,
    model_year TEXT,
    mileage TEXT,
    engine TEXT,
    power TEXT,
    displacement TEXT,
    transmission TEXT,
    condition TEXT,
    owner TEXT,
    service_book TEXT,
    garaged TEXT,
    in_traffic_since TEXT,
    first_registration_in_croatia TEXT,
    registered_until TEXT,
    fuel_consumption TEXT,
    eco_category TEXT,
    number_of_gears TEXT,
    warranty TEXT,
    average_CO2_emission TEXT,
    video_call_viewing TEXT,
    gas TEXT,
    auto_warranty TEXT,
    number_of_doors TEXT,
    chassis_type TEXT,
    number_of_seats TEXT,
    drive_type TEXT,
    color TEXT,
    metalic_color TEXT,
    suspension TEXT,
    tire_size TEXT,
    internal_code TEXT
);
""")