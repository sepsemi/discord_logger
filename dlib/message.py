from .user import User

class Message:

    def __init__(self, state, channel, data):
        self._state = state
        self.channel = channel
        self.id = int(data['id'])
        self.author = User(state=state, data=data['author'])
        self.content = data['content']


