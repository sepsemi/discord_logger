import ujson
import uvloop
import asyncio
import asyncpg
import logging

from src.database import DiscordDatabase

import dlib

with open('etc/config.json') as fp:
    config = ujson.load(fp)


logger = logging.getLogger('dlib')

logger.setLevel(logging.INFO)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(name)s - %(message)s'))
logger.addHandler(sh)


class DiscordClient(dlib.Client):
    async def on_ready(self):
        print('[{}] ready: {}, {}'.format(self.id, self.user.id, self.user))

    async def on_new_user(self, ctx):
       await self._database.insert_user(ctx) 

    async def on_message(self, ctx):
        await self._database.insert_message(ctx)
        print('[{}] message: {}, {}:{}, {}, {}'.format(self.id, ctx.channel.guild, ctx.channel.name, ctx.author.id, ctx.author, ctx.content))

async def main(loop):
    tasks = set()
    database = DiscordDatabase(loop = loop, **config['database'])
    # Create the database pool for the clients
    await database.create_pool()
    
    with open('etc/tokens.txt', 'r') as fp:
        for line in fp.readlines():
            client = DiscordClient(loop = loop)
            client._database = database
            token = line.strip()
            
            tasks.add(loop.create_task(client.connect(token = token)))

    # Start handling dead clients
    print('Loaded {} clients'.format(len(tasks)))
    await asyncio.wait(tasks)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main(loop))

