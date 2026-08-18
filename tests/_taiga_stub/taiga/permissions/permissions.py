class HasProjectPerm:
    def __init__(self, *args, **kwargs):
        pass

    def __and__(self, other):
        return self

    def __or__(self, other):
        return self

    def __invert__(self):
        return self


class IsProjectAdmin:
    def __init__(self, *args, **kwargs):
        pass

    def __and__(self, other):
        return self

    def __or__(self, other):
        return self

    def __invert__(self):
        return self
