"""The start of ``claudia-server.exe``: ``python -m claudia_server`` for a program that has no ``python`` (D730).

The server runs its slow work in a pool of processes (``claudia_server.workers``). On Windows a pool starts its workers
by running this very program again with ``--multiprocessing-fork`` and a few more words; ``freeze_support`` is what
answers those words and sends such a process to its work instead of starting a second server.
"""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from claudia_server.cli import main

    sys.exit(main())
