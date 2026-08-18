class DefaultRouter:
    instances = []

    def __init__(self, trailing_slash=True):
        self.trailing_slash = trailing_slash
        self.registry = []
        DefaultRouter.instances.append(self)

    def register(self, prefix, viewset, base_name=None):
        self.registry.append((prefix, viewset, base_name))

    @property
    def urls(self):
        return []
