import shlex
import subprocess

from constants import (
    BRACES_PLACEHOLDER_REGEX,
    PERCENT_PLACEHOLDER_REGEX,
    RESX_FILE_REGEX,
)


def _percent_to_braces(match):
    n = int(match[1])
    return f"{{{n-1}}}"  # {0} for example


def _braces_to_percent(match):
    n = int(match[1])
    return f"%{n+1}"


def convert_braces_to_percents(string):
    return BRACES_PLACEHOLDER_REGEX.sub(_braces_to_percent, string)


def convert_percents_to_braces(string):
    return PERCENT_PLACEHOLDER_REGEX.sub(_percent_to_braces, string)


def file_updated(file_path):
    return True
    quoted_file_path = shlex.quote(str(file_path))
    return_code = subprocess.call(
        ["bash", "-c", f"[[ $(git diff HEAD~1  -- {quoted_file_path}) ]]"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 0 means we have some diff
    return return_code == 0


def parse_resx_filename(resx_filename):
    match = RESX_FILE_REGEX.match(resx_filename)
    return match[1], match[2]


def get_percent_placeholders(string):
    return PERCENT_PLACEHOLDER_REGEX.findall(string)
