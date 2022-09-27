class Guild:
    
    def __init__(self, state, data):
        self.channels = {}
        self.members = {}
        self._state = state
        
        # Data
        self.id = int(data['id'])
        self.name = data['name']
        self.verification_level = int(data['verification_level'])
        self._icon = data['icon']
        self._banner = data['banner']
        self.emojis = data['emojis']
        self.description = data['description']
        self.vanity_url_code = data['vanity_url_code']
        self._discovery_splash = data['discovery_splash']
        self.owner_id = int(data['owner_id'])
    
        for channel in data['channels']:
            pass
