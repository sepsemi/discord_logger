import asyncpg

class Database:

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        self._pool = None
        

    async def create_pool(self):
        # Bootstrap function
        self._pool = await asyncpg.create_pool(
            host = self.host,
            port = self.port,
            user = self.user,
            password = self.password,
            database = self.database
        )

    async def insert(self, sql, values):
        # Hide the insert errors from the end user
        async with self._pool.acquire() as connection:
            try:
                await connection.execute(sql, *values)
            except asyncpg.exceptions.UniqueViolationError:
                # Yeah but who really cares?
                return None

class DiscordDatabase(Database):

    def __init__(self, loop, **kwargs):
        Database.__init__(self, **kwargs)
        self.loop = loop

    async def insert_user(self, data):
        sql = """
            INSERT INTO users(id, username, discriminator, avatar, bot, system, banner, flags, premium_type, public_flags)
            VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        await self.insert(sql, data.values())

        
