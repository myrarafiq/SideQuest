-- SideQuest schema. Seven tables.
-- Entity -> table. 1:N -> foreign key. M:N -> bridge table.
--
-- Activities are the things to do. A room is the saved hangout.
-- A blank user_id on preferences means the whole group.
-- The chosen plan, the decision timer, and each person's one free window
-- are columns, not extra tables.

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
    status TEXT,
    min_age INTEGER,
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

CREATE TABLE rooms (
    room_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'voting', 'matched', 'archived')),
    organizer_user_id INTEGER NOT NULL REFERENCES users (user_id),
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    planning_start TIMESTAMP WITH TIME ZONE,
    planning_end TIMESTAMP WITH TIME ZONE,
    vote_deadline TIMESTAMP WITH TIME ZONE,
    chosen_activity_id INTEGER REFERENCES activities (activity_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- One person can be in many rooms, and a room has many people.
-- Budget, travel, and the free window are one value per person per room.
CREATE TABLE room_members (
    room_id INTEGER NOT NULL REFERENCES rooms (room_id),
    user_id INTEGER NOT NULL REFERENCES users (user_id),
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('organizer', 'member', 'guest')),
    ready BOOLEAN NOT NULL DEFAULT FALSE,
    budget_hard NUMERIC,
    budget_ideal NUMERIC,
    budget_currency TEXT,
    budget_includes_transport BOOLEAN NOT NULL DEFAULT FALSE,
    travel_limit_minutes INTEGER,
    travel_mode TEXT CHECK (travel_mode IS NULL OR travel_mode IN ('transit', 'walking', 'either')),
    starting_area TEXT,
    indoor_outdoor TEXT CHECK (indoor_outdoor IS NULL OR indoor_outdoor IN ('indoor', 'outdoor', 'either')),
    free_start TIMESTAMP WITH TIME ZONE,
    free_end TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (room_id, user_id),
    CHECK (free_end IS NULL OR free_start IS NULL OR free_end > free_start)
);

-- Many tastes per person, and tastes the whole room shares.
-- user_id blank = the group. hard + require/exclude = vegan, no BBQ.
-- flexible + prefer/avoid = not into horror, but will go if the group is.
CREATE TABLE preferences (
    preference_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms (room_id),
    user_id INTEGER REFERENCES users (user_id),
    category_id INTEGER REFERENCES categories (category_id),
    label TEXT,
    polarity TEXT NOT NULL CHECK (polarity IN ('require', 'prefer', 'avoid', 'exclude')),
    strength TEXT NOT NULL CHECK (strength IN ('hard', 'flexible')),
    CHECK (category_id IS NOT NULL OR label IS NOT NULL),
    CHECK (
        (strength = 'hard' AND polarity IN ('require', 'exclude'))
        OR (strength = 'flexible' AND polarity IN ('prefer', 'avoid'))
    )
);
