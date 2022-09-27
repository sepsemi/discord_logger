import time
import logging
import asyncio

from .state import ConnectionState
from .gateway import DiscordWebsocket

_log = logging.getLogger(__name__)

class Client:
    
    def __init__(self, loop, max_reconnects = 10):
        self.loop = loop
        self.ws = None
        self.http = None
        self._listeners = {}
        self._closed = False
        self.max_reconnects = max_reconnects
        self._reconnects = 0

        # Stuff
        self._connection = ConnectionState(
            dispatch = self.dispatch,
            http = None,
            loop = self.loop
        )

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

    async def connect(self, token, reconnect = True):
        self.id = token[:18]
        self.token = token
        ws_params = {
            'initial': True
        } 
        while not self._reconnects == self.max_reconnects:
            ws = DiscordWebsocket(client = self, loop = self.loop)
            
            # Run forever untill reconnect
            await ws.long_poll()

            # Connection was reset
            self._reconnects +=1
    
    def event(self, coro):
        setattr(self, coro.__name__, coro)
        _log.debug('%s has successfully been registered as an event', coro.__name__)    
    
    @property
    def user(self):
        return self._connection.user

    @property
    def users(self):
        return list(self._connection.users.values())

