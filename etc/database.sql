CREATE TABLE users (
    id BIGINT PRIMARY KEY NOT NULL,
    username VARCHAR(32) NOT NULL,
    discriminator VARCHAR(4) NOT NULL,
    avatar VARCHAR(32) NOT NULL,
    bot BOOLEAN NOT NULL,
    system BOOLEAN NOT NULL,
    banner VARCHAR(32) NOT NULL,
    flags SMALLINT NOT NULL,
    premium_type SMALLINT NOT NULL,
    public_flags SMALLINT NOT NULL

);

CREATE TABLE messages (
    id BIGINT PRIMARY KEY NOT NULL,
    type SMALLINT NOT NULL,
    timestamp BIGINT NOT NULL,
);
