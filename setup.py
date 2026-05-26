"""Setuptools compatibility hooks for platform-specific release wheels."""

from __future__ import annotations

from pathlib import Path

from setuptools import setup

try:
    from wheel.bdist_wheel import bdist_wheel
except ImportError:  # pragma: no cover - wheel is present in normal builds
    setup()
else:

    class PlatformWheel(bdist_wheel):
        """Mark release wheels as platform-specific when a bundled binary is staged."""

        def _has_bundled_payload(self) -> bool:
            bundled = Path(__file__).parent / "src" / "ebolasim" / "_bundled"
            return any(path.is_file() and path.name != ".gitkeep" for path in bundled.rglob("*"))

        def finalize_options(self) -> None:
            super().finalize_options()
            if self._has_bundled_payload():
                self.root_is_pure = False

        def get_tag(self) -> tuple[str, str, str]:
            python_tag, abi_tag, platform_tag = super().get_tag()
            if self._has_bundled_payload():
                return "py3", "none", platform_tag
            return python_tag, abi_tag, platform_tag

    setup(cmdclass={"bdist_wheel": PlatformWheel})
