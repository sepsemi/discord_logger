import json
import zlib
import asyncio
import websockets

class DiscordWebsocket:
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_MEMBERS = 8
    INVALIDATE_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12   

    def __init__(self, loop, client):
        self.loop = loop
        self.id = client.id
        self.token = client.token
        self.uri = 'wss://gateway.discord.gg/?encoding=json&v=9&compress=zlib-stream'
            
        self._connection = client._connection
        self._discord_parsers = client._connection.parsers
        self._dispatch = client.dispatch

        # ws related stuff
        self.ws_timeout = 30.0
        self.session_id = None
        self.sequence = None
        self._zlib = zlib.decompressobj()
        self._buffer = bytearray()
        self._close_code = None

    async def received_message(self, websocket, msg):
        if type(msg) is bytes:
            self._buffer.extend(msg)
            if len(msg) < 4 or msg[-4:] != b'\x00\x00\xff\xff':
                return None

            msg = self._zlib.decompress(self._buffer)
            # Legacy reasons..
            msg = msg.decode('utf-8')
            self._buffer = bytearray()

        msg = json.loads(msg)

        op = msg['op'] if 'op' in msg.keys() else None
        data = msg['d'] if 'd' in msg.keys() else None
        seq = msg['s'] if 's' in msg.keys() else None
        event = msg['t'] if 't' in msg.keys() else None
        
        if op != self.DISPATCH:
            if op == self.RECONNECT:
                return None

            if op == self.HEARTBEAT_ACK:
                return None

            if op == self.HEARTBEAT:
                return None

            if op == self.HELLO:
                interval = data['heartbeat_interval'] / 1000.0
                self.ws_timeout = interval

                self._keep_alive = None

                # Send identify
                await self.identify(websocket)

                # Send a heartbeat immediatly
                return None
        
        if event == 'READY':
            #print('client {} ready.'.format(self.id))
            await self.change_presence(websocket)

        elif event == 'RESUMED':
            return None

        try:
            func = self._discord_parsers[event]
        except KeyError:
            # Unknown event
            return None
        else:
            func(data)

    async def change_presence(self, websocket):
        # Just here to exist and fake change_presence
        payload = {
            'op': 3,
            'd': {
                'status': 'online',
                'since': 0,
                'activities': [
                    {
                        'name': 'Custom Status',
                        'type': 4,
                        'state': 'Hopelessly Devoted to You',
                        'emoji': None
                    }
                ],
                'afk': False
            }
        }
        await websocket.send(json.dumps(payload))

    async def identify(self, websocket):
        # This is highly unreliable
        payload = {
            'op': self.IDENTIFY,
            'd': {
                'token': self.token,
                'capabilities': 1021,
                'properties': {
                    'os': 'Linux',
                    'browser': 'Chrome',
                    'device': "",
                    'system_locale': 'en-US',
                    'browser_user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
                    'browser_version': '100.0.4896.127',
                    'os_version': '',
                    'referrer': '',
                    'referring_domain': '',
                    'referrer_current': '',
                    'referring_domain_current': '',
                    'release_channel': 'stable',
                    'client_build_number': 149345,
                    'client_event_source': None
                },
                'compress': False,
                # Need to research
                'client_state': {
                    'guild_hashes': {},
                    'highest_last_message_id': '0',
                    'read_state_version': 0,
                    'user_guild_settings_version': -1,
                    'user_settings_version': -1,
                    'private_channels_version': '0'
                }
            }
        }

        # Set presence
        payload['d']['presence'] = {
            'status': 'online',
            'since': 0,
            'activities': [],
            'afk': False
        }
        await websocket.send(json.dumps(payload))

    async def long_poll(self, resume = False):
        size = 1024 * 1024 * 2.5
        ws_params = {
            'max_size': size,
            'read_limit': size,
            'write_limit': size
        }
        async with websockets.connect(self.uri, **ws_params) as websocket:
            try:
                while True:
                    msg = await asyncio.wait_for(websocket.recv(), timeout = self.ws_timeout)
                    await self.received_message(websocket, msg)

            except (asyncio.exceptions.TimeoutError) as e:
                print('gateway message timeout')

