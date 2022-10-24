import time
import logging
import asyncio
import websockets

from .device import create_devices

from .backoff import ExponentialBackoff
from .state import ConnectionState
from .gateway import DiscordWebsocket, ReconnectWebSocket

_log = logging.getLogger(__name__)

DEVICES = create_devices()


class Client:
    
    def __init__(self, loop, token):
        self.loop = loop
        self.token = token
        self.id = token[:16]
        self.ws = None
        self.http = None
        self._listeners = {}
        self._closed = False
        self.max_reconnects = 10
        self._reconnects = 0

        # Instantiate the state manager
        self._connection = ConnectionState(
            dispatch = self.dispatch,
            http = None,
            loop = self.loop
        )
        # Late to the game i guess?
        self._connection.id = self.id

        # Fetch a device from the poo
        self._device = DEVICES.pop(0)

    async def _run_event(self, coro, event_name, *args, **kwargs):
        await coro(*args, **kwargs)

    def _schedule_event(self, coro, event_name, *args, **kwargs):
        wrapped = self._run_event(coro, event_name, *args, **kwargs)
        
        # Schedules the task
        return asyncio.create_task(wrapped, name = event_name)

    def dispatch(self, event, *args, **kwargs):
        method = 'on_{}'.format(event)
        coro = getattr(self, method)

        self._schedule_event(coro, method, *args, **kwargs)
    
    @property
    def _ws_client_params(self):
        size = 1024 * 1024 * 2.5

        return {
            'max_size': size,
            'read_limit': size,
            'write_limit': size
        }

    async def connect(self):
        backoff = ExponentialBackoff()

        ws_params = {
            'initial': True,
        }
        while not self._reconnects == self.max_reconnects:
            # Run forever untill max reconnects
            ws = DiscordWebsocket(client=self,loop = self.loop, params=ws_params)

            async with websockets.connect(ws.uri, **self._ws_client_params) as sock:
                while True:
                    try:
                        await ws.poll_event(sock) 
                    except ReconnectWebSocket as e:
                        _log.debug('[{}] gateway: got a request to {}'.format(self.id, e.op.lower()))
                        ws_params.update(sequence=ws.sequence, resume=e.resume, session=ws.session_id)
                        break # We exit the main dataflow and create a new connection

                self._reconnects+=1
                retry = backoff.delay()

                _log.info("Attempting a reconnect in %.2fs", retry)
                await asyncio.sleep(retry)

    def event(self, coro):
        setattr(self, coro.__name__, coro)
        _log.debug('%s has successfully been registered as an event', coro.__name__)    
    
    @property
    def user(self):
        return self._connection.user

    @property
    def users(self):
        return list(self._connection.users.values())

