CREATE TABLE users (
    id BIGINT PRIMARY KEY NOT NULL,
    username VARCHAR(32) NOT NULL,
    discriminator VARCHAR(4) NOT NULL,
    avatar VARCHAR(32) NOT NULL,
    bot BOOLEAN NOT NULL,
    system BOOLEAN NOT NULL,
    public_flags SMALLINT NOT NULL
);

CREATE TABLE messages (
    id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL, 
    type SMALLINT DEFAULT 0 NOT NULL,
    state SMALLINT DEFAULT 0 NOT NULL,
    mention_everyone BOOLEAN DEFAULT FALSE NOT NULL,
    has_attachments BOOLEAN DEFAULT FALSE NOT NULL,
    has_embeds BOOLEAN DEFAULT FALSE NOT NULL,
    has_components BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    content TEXT DEFAULT '' NOT NULL,
    PRIMARY KEY(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
);

-- We create the trigger to update messages.updates_at 
CREATE  FUNCTION update_updated_at_messages()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_messages_updated_at
    BEFORE UPDATE
    ON
        messages
    FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_messages();
