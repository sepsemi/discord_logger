import zlib
import time
import random
import logging
import asyncio
import datetime
import threading
import websockets

from .utils import minutes_elapsed_timestamp, to_json, from_json

_log = logging.getLogger(__name__)

class AsyncKeepaliveHandler:
    WINDOW = 2.0

    def __init__(self, websocket, interval, socket):
        self.websocket = websocket
        self.interval = interval
        self.socket = socket
        self.id = websocket.id
        self.heartbeat_timeout = websocket._max_heartbeat_timeout

        # Predefined messages
        self.msg = '[%s] keepalive: heartbeat send, sequence=%s'
        self.behind_msg = '[%s] keealive: Gateway acknowledged late %.1fs behind'

        # Metric data
        timestamp = time.perf_counter()
        self._last_send = timestamp
        self._last_ack = timestamp
        self._last_recv = timestamp
        self.latency = float('inf')

    def ack(self):
        ack_time = time.perf_counter()
        self._last_ack = ack_time
        self.latency = ack_time - self._last_send

        if self.latency > 10:
            _log.warn(self.behind_msg % (self.websocket.id, self.latency))
        else:
            _log.debug(self.msg % (self.id, self.websocket.sequence))

    def tick(self):
        self._last_recv = time.perf_counter()

    def get_payload(self):
        return {
            'op': self.websocket.HEARTBEAT,
            'd': self.websocket.sequence
        }

    async def run(self):
        while True:
            if self._last_recv + self.heartbeat_timeout < time.perf_counter():
                _log.warn('[{}] keepalive: has stopped responding to gateway, closing'.format(self.id))
                self.websocket.is_closed = True
                return None

            data = self.get_payload()
            try:
                # Send the payload to the websocket and quit if timeout

                await asyncio.wait_for(self.socket.send(to_json(data)), timeout=self.WINDOW)
                self._last_send = time.perf_counter()

            except (asyncio.exceptions.TimeoutError, websockets.exceptions.ConnectionClosedOK):
                self.websocket.is_closed = True
                _log.warn('[{}] keepalive: error, closing connection'.format(self.id))
                return None

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
        self._device = client._device

        # ws related stuff
        self._keep_alive = None
        self.is_closed = False
        self.session_id = None
        self.sequence = None
        self._max_heartbeat_timeout = client._connection.heartbeat_timeout
        self._zlib = zlib.decompressobj()
        self._buffer = bytearray()
        self._close_code = None

    def clean(self):
        # Clean up after ourselfs
        self._keep_alive = None
        self.is_closed = False
        self.session_id = None
        self.sequence = None
        self._zlib = bytearray()
        self._buffer = bytearray()
        self._close_code = None

    async def received_message(self, socket, msg):
        if type(msg) is bytes:
            self._buffer.extend(msg)
            if len(msg) < 4 or msg[-4:] != b'\x00\x00\xff\xff':
                return None

            msg = self._zlib.decompress(self._buffer)
            self._buffer = bytearray()
        
        msg = from_json(msg)
        
        event = msg['t'] if 't' in msg.keys() else None

        op = msg['op'] if 'op' in msg.keys() else None
        data = msg['d'] if 'd' in msg.keys() else None
        seq = msg['s'] if 's' in msg.keys() else None
        
        if seq is not None:
            self.sequence = seq

        if self._keep_alive:
            self._keep_alive.tick()
 
        if op != self.DISPATCH:
            if op == self.RECONNECT:
                # We just treat it as a lazy close and reconnect
                # Keepalive will die, eventually..
                
                self.is_closed = True
                _log.debug('[{}] gateway: Asked for reconnect'.format(self.id))

            if op == self.HEARTBEAT_ACK:            
                self._keep_alive.ack()

            if op == self.HEARTBEAT:
                await self._keep_alive.send_heartbeat(self.id)    
                _log.debug('[{}] gateway: Request forcefull hearbeat send'.format(self.id))
            
            if op == self.HELLO:
                interval = data['heartbeat_interval'] / 1000.0

                # Send identify
                await self.identify(socket)
                 
                self._keep_alive = AsyncKeepaliveHandler(websocket=self, interval=interval, socket=socket)
                self.loop.create_task(self._keep_alive.run())
            
            if op == self.INVALIDATE_SESSION:
                _log.info('[{}] gateway: Invalidated session'.format(self.id))

                # Set to null
                self.sequence = None
                self.session_id = None     
                
                # Signal close (Lazy)
                self.is_closed = True
        
        if event == 'READY':
            # Update our prescence as we connect
            await self.change_presence(socket)

        elif event == 'RESUMED':
            _log.debug('[{}] gateway: has resumed'.format(self.id))

        try:
            func = self._discord_parsers[event]
        except KeyError:
            if event is not None:
                _log.debug('[{}] gateway: unsubscribed event seq={}, event={}'.format(self.id, seq, event)) 
        else:
            func(data)

    async def change_presence(self, socket):
        # Create an elapsed timestamp for exmaple "20-60 minutes"
        elapsed = minutes_elapsed_timestamp(random.randint(20,60))

        payload = {
            'op': self.PRESENCE,
            'd': {
                'status': 'online',
                'since': None,
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
        await socket.send(to_json(payload))

    async def identify(self, socket):
        # This is highly unreliable
        payload = {
            'op': self.IDENTIFY,
            'd': {
                'token': self.token,
                'capabilities': 1021,
                'properties': {**self._device},
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
        
        await socket.send(to_json(payload))

    async def long_poll(self, resume = False):
        size = 1024 * 1024 * 2.5
        ws_params = {
            'max_size': size,
            'read_limit': size,
            'write_limit': size
        }

        async with websockets.connect(self.uri, **ws_params) as socket:
            while not self.is_closed:
                try:
                    msg = await asyncio.wait_for(socket.recv(), timeout = self._max_heartbeat_timeout)
                    await self.received_message(socket, msg)

                except asyncio.exceptions.TimeoutError as e:
                    _log.error('[{}] gateway: receive timeout'.format(self.id))
                    self.clean()
                    break # No point in proceeding, close connection by client handler
