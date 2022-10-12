import json
import zlib
import time
import logging
import asyncio
import threading
import websockets

_log = logging.getLogger(__name__)

class AsyncKeepaliveHandler:
    WINDOW = 2.0

    def __init__(self, websocket, interval, socket):
        self.open = False
        self.websocket = websocket
        self.interval = interval
        self.socket = socket

        # Predefined messages
        self.msg = '[%s] keepalive: heartbeat send, sequence=%s'
        self.behind_msg = '[%s] keealive: Gateway acknowledged late %.1fs behind'

        # Metric data
        timestamp = time.perf_counter()
        self.last_send = timestamp
        self.last_ack = timestamp
        self.last_recv = timestamp
        self.latency = float('inf')

    def ack(self):
        ack_time = time.perf_counter()
        self.last_ack = ack_time
        self.latency = ack_time - self.last_send

        if self.latency > 10:
            _log.warn(self.behind_msg % (self.websocket.id, self.latency))
        else:
            _log.info(self.msg % (self.websocket.id, self.websocket.sequence))

    def tick(self):
        self._last_recv = time.perf_counter()

    def get_payload(self):
        return {
            'op': self.websocket.HEARTBEAT,
            'd': self.websocket.sequence
        }

    async def run(self):
        self.open = True

        while self.open:
            payload = self.get_payload()
            
            # Send the payload to the websocket and quit if timeout
            try:
                await asyncio.wait_for(self.socket.send(json.dumps(payload)), timeout=self.WINDOW)
                self.last_send = time.perf_counter()
            except asyncio.excetions.TimeoutError:
                _log.warn('[{}] keepalive: timeout on send, ignored for now'.format(self.id))
                break;

            await asyncio.sleep(self.interval - self.WINDOW)

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

    async def received_message(self, socket, msg):
        if type(msg) is bytes:
            self._buffer.extend(msg)
            if len(msg) < 4 or msg[-4:] != b'\x00\x00\xff\xff':
                return None

            msg = self._zlib.decompress(self._buffer)
            # Legacy reasons..
            msg = msg.decode('utf-8')
            self._buffer = bytearray()

        msg = json.loads(msg)
        
        event = msg['t'] if 't' in msg.keys() else None

        op = msg['op'] if 'op' in msg.keys() else None
        data = msg['d'] if 'd' in msg.keys() else None
        seq = msg['s'] if 's' in msg.keys() else None
        
        if seq is not None:
            self.sequence = seq
 
        if op != self.DISPATCH:
            if op == self.RECONNECT:
                _log.debug('[{}] gateway: Asked for reconnect'.format(self.id))

            if op == self.HEARTBEAT_ACK:            
                self._keep_alive.ack()

            if op == self.HEARTBEAT:
                await self._keepalive_handler.send_heartbeat(self.id)    
                _log.debug('[{}] gateway: Request forcefull hearbeat send'.format(self.id))
            
            if op == self.HELLO:
                interval = data['heartbeat_interval'] / 1000.0
                self.ws_timeout = interval

                # Send identify
                await self.identify(socket)
                 
                self._keep_alive = AsyncKeepaliveHandler(websocket=self, interval=interval, socket=socket)
                self.loop.create_task(self._keep_alive.run())
        
        if event == 'READY':
            #print('client {} ready.'.format(self.id))
            #await self.change_presence(socket)
            await self.update_presence(socket)

        elif event == 'RESUMED':
            _log.debug('[{}] gateway: has resumed'.format(self.id))

        try:
            func = self._discord_parsers[event]
        except KeyError:
            if event is not None:
                _log.debug('[{}] gateway: unsubscribed event seq={}, event={}'.format(self.id, seq, event)) 
        else:
            func(data)

    async def update_presence(self, socket):
        # The current time in miliseconds (Not precice)
        timestamp = int(time.time() * 1000 + 0.1)
        # Create an elapsed timestamp for exmaple "20 minutes"
        elapsed = timestamp -  1200 * 1000 

        payload = {
            'op': self.PRESENCE,
            'd': {
                'status': 'online',
                'since': 0,
                'activities': [
                    {
                        'name': 'Custom Status',
                        'type': 4,
                        'state': 'Hopelessly Devoted to You',
                        'emoji': None
                    },
                    {   
                        'name': 'Hearts of Iron IV',
                        'type': 0,
                        'application_id': 358421669603311616,
                        'timestamps': {
                            'start': elapsed
                        }
                    }
                ],
                'afk': False
            }
        }
        await socket.send(json.dumps(payload))

    async def change_presence(self, socket):
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
        await socket.send(json.dumps(payload))

    async def identify(self, socket):
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

        await socket.send(json.dumps(payload))

    async def long_poll(self, resume = False):
        size = 1024 * 1024 * 2.5
        ws_params = {
            'max_size': size,
            'read_limit': size,
            'write_limit': size
        }

        async with websockets.connect(self.uri, **ws_params) as socket:
            while True:
                try:
                    msg = await asyncio.wait_for(socket.recv(), timeout = self.ws_timeout)
                    await self.received_message(socket, msg)

                except asyncio.exceptions.TimeoutError as e:
                    _log.error('[{}] gateway: receive timeout'.format(self.id))
                    continue
                    # break

