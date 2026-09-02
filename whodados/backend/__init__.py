"""Pacote whodados.backend — endpoints FastAPI."""
# Imports lazy para evitar circularidade no carregamento do módulo.
__all__ = ["app", "router"]


def __getattr__(name):
    if name == "app":
        from backend.main import app as _app
        return _app
    if name == "router":
        from backend.endpoints import router as _router
        return _router
    raise AttributeError(f"module 'backend' has no attribute {name!r}")
