class BaseUser:
    __slots__  = (
        'name',
        'id',
        'discriminator',
        '_avatar',
        'bot',
        'system',
        '_public_flags',
        '_state'
    )

    def __init__(self, state, data):
        self._state = state
        self.id = int(data['id'])
        self.name = data['username']
        self.discriminator = data['discriminator']
        self._avatar = data['avatar']
        self._public_flags = data.get('public_flags', 0)
        self.bot = data.get('bot', False)
        self.system = data.get('system', False)
    
    def __repr__(self) -> str:
        return (
            f"<BaseUser id={self.id} name={self.name!r} discriminator={self.discriminator!r}"
            f" bot={self.bot} system={self.system}>"
        )

    def __str__(self) -> str:
        return f'{self.name}#{self.discriminator}'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _UserTag) and other.id == self.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return self.id >> 22

class ClientUser(BaseUser):
    __slots__ = ('locale', '_flags', 'verified', 'mfa_enabled', '__weakref__')

    def __init__(self, state, data):
        super().__init__(state=state, data=data)
        self.verified = data.get('verified', False)
        self.locale = data.get('locale')
        self._flags = data.get('flags', 0)
        self.mfa_enabled = data.get('mfa_enabled', False)

class User(BaseUser):

    __slots__ = ('__weakref__',)
