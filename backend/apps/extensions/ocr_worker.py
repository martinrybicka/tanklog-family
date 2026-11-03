"""Samostatný proces s omezenými prostředky; nepřebírá konfiguraci ani secrets Django."""

import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
if sys.platform.startswith("linux"):
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
os.umask(0o077)
os.execv(sys.argv[1], sys.argv[1:])
