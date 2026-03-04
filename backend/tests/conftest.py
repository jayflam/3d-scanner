"""Shared test fixtures and module stubs.

This conftest installs proper mocks for heavy dependencies (Celery, Redis,
torch, etc.) before any test module imports application code.  The Celery
mock provides a pass-through ``task()`` decorator so that decorated functions
remain callable (instead of becoming MagicMock instances).
"""

from __future__ import annotations

import sys
from functools import wraps
from unittest.mock import MagicMock


# ── Celery mock with pass-through task() decorator ──────────────────────────

class _FakeCeleryApp:
    """Minimal Celery stand-in whose ``.task()`` returns the real function."""

    conf = MagicMock()
    autodiscover_tasks = MagicMock()

    def task(self, *args, **kwargs):
        """Decorator that preserves the original function."""
        bind = kwargs.get("bind", False)

        def decorator(fn):
            @wraps(fn)
            def wrapper(*a, **kw):
                if bind:
                    # Inject a fake `self` when called without one
                    mock_self = MagicMock()
                    mock_self.request.id = "test-celery-id"
                    return fn(mock_self, *a, **kw)
                return fn(*a, **kw)

            # Preserve access to the raw function
            wrapper.__wrapped__ = fn
            wrapper.delay = MagicMock()
            wrapper.apply_async = MagicMock()
            wrapper.s = MagicMock()
            wrapper.si = MagicMock()
            return wrapper

        # Support both @celery.task and @celery.task(...)
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


_fake_celery_module = MagicMock()
_fake_celery_module.Celery = _FakeCeleryApp

# Install BEFORE any app code is imported
sys.modules.setdefault("celery", _fake_celery_module)
sys.modules.setdefault("celery.result", MagicMock())

# Also pre-install the celery_app module so imports get our fake app
_fake_celery_app_instance = _FakeCeleryApp()
_fake_celery_app_mod = MagicMock()
_fake_celery_app_mod.celery = _fake_celery_app_instance
sys.modules.setdefault("app.tasks.celery_app", _fake_celery_app_mod)

# ── Other heavy dependency stubs ────────────────────────────────────────────

for mod in ("torch", "trimesh", "trimesh.visual", "trimesh.visual.material",
            "xatlas", "einops"):
    sys.modules.setdefault(mod, MagicMock())

fake_tsr = MagicMock()
sys.modules.setdefault("tsr", fake_tsr)
sys.modules.setdefault("tsr.system", fake_tsr.system)
sys.modules.setdefault("tsr.bake_texture", fake_tsr.bake_texture)

fake_rembg = MagicMock()
fake_rembg.remove = lambda img, **kw: img.convert("RGBA")
fake_rembg.new_session = MagicMock(return_value=MagicMock())
fake_rembg.sessions = MagicMock()
sys.modules.setdefault("rembg", fake_rembg)
sys.modules.setdefault("rembg.sessions", fake_rembg.sessions)

# Stub deps not always installed in test environments
for mod in ("cv2", "redis", "ffmpeg", "weasyprint"):
    sys.modules.setdefault(mod, MagicMock())
