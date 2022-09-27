
class PrivateChannel:

    def __init__(self, me, state, data):
        self.type = int(data['type'])
        self.id = int(data['id'])
        self.flags = int(data['flags'])
        self.recipients = [state._users[int(uid)] for uid in data['recipient_ids']]

    def __str__(self):
         return 'Direct message with {}'.format(self.recipients[0])

class DMChannel:

    def __init__(self, me, state, data):
        self._state = state
        self.recipient = data['recipients'][0]
        self.me = me
        self.id = int(data['id'])

    def __str__(self) -> str:
        if self.recipient:
            return f'Direct Message with {self.recipient}'
        return 'Direct Message with Unknown User'

    @classmethod
    def _from_message(cls, state, channel_id):
        self = cls.__new__(cls)
        self._state = state
        self.id = channel_id
        self.recipient = None
        self.me = state.user
        return self

