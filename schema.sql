-- SideQuest practice schema.
-- Entity -> table. 1:N -> foreign key. M:N -> bridge table.
-- Parks events, Ticketmaster events, and Google places are one activities entity.

CREATE TABLE users (
    user_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER CHECK (age IS NULL OR age BETWEEN 1 AND 120)
);

CREATE TABLE activities (
    activity_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    starttime TIMESTAMP WITH TIME ZONE,
    endtime TIMESTAMP WITH TIME ZONE,
    timezone TEXT,
    price_currency TEXT,
    price_min NUMERIC,
    price_max NUMERIC,
    url TEXT,
    collected_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (source, source_item_id)
);

CREATE TABLE categories (
    category_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE activity_categories (
    activity_id INTEGER NOT NULL REFERENCES activities (activity_id),
    category_id INTEGER NOT NULL REFERENCES categories (category_id),
    PRIMARY KEY (activity_id, category_id)
);
