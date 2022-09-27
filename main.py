import ujson
import uvloop
import asyncio

import dlib

class DiscordClient(dlib.Client):
    async def on_ready(self):
        print('ready() id = {}, username = {} userid = {}'.format(self.id, self.user, self.user.id)) 

    async def on_message(self, ctx):
        author_name = ctx.author.name.encode('unicode-escape').decode()
        content = ctx.content.encode('unicode-escape').decode()
        print('client_id = {}, channel_name={} author={} content = {}'.format(self.id, ctx.channel, author_name, content))

async def main(loop):
    clients = set()
    with open('etc/tokens.txt', 'r') as fp:
        for line in fp.readlines():
            client = DiscordClient(loop = loop)
            token = line.strip()

            clients.add(loop.create_task(client.connect(token = token)))

    # Start handling dead clients
    await asyncio.wait(clients)
    print('clients died')
    

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main(loop))
