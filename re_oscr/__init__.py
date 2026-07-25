__all__ = ['REOSCRApplication']


def __getattr__(name):
    """Keep child-only presentation imports from loading the parser application."""
    if name == 'REOSCRApplication':
        from .app import REOSCRApplication
        return REOSCRApplication
    raise AttributeError(name)
