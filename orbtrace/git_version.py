import functools
import subprocess
import re

@functools.cache
def get_version():
    return subprocess.check_output('git describe --always --long --dirty', shell = True).decode('utf-8').strip()

def get_version_bcd():
    m = re.match(r'v(\d{1,2})\.(\d)(?:\.(\d+))?-', get_version())

    if not m:
        raise ValueError('Version doesn\'t match pattern representable as BCD')

    major, minor, patch = m.groups()

    return int(major) + int(minor) * 0.1 + int(patch or 0) * 0.01
