"""Frozen Maia-3 UCI sidecar.

The Windows bundle contains a small second executable for Maia. Keeping the
UCI process separate from the Move Coach launcher means PyInstaller can ship
PyTorch and Maia's native libraries without importing them into the browser
daemon process.
"""

from maia3.uci import main


if __name__ == '__main__':
    main()
