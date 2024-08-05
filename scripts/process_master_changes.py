import json
import os
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from constants import EMAIL_ADDRESS
from utils import (
    convert_braces_to_percents,
    convert_percents_to_braces,
    file_updated,
    parse_resx_filename,
)

REPOSITORY_DIR = Path(".")
PROJECTS_DIR = Path(os.environ["PROJECTS_DIR"])


def process_project(project_path):
    convert_resx_files(project_path)
    generate_pot_file(project_path)


def convert_resx_files(project_path):
    english_files = []
    has_changes = False
    for file in project_path.glob("*.resx"):
        if parse_resx_filename(file.name)[1] is None:
            english_files.append(file)
            if not has_changes and file_updated(file):
                has_changes = True
    if not has_changes:
        return
    lng = {"Culture": "en", "Language": "english"}
    for file in english_files:
        lng |= parse_resx(file)
    lng = json.dumps(lng, indent=2, ensure_ascii=False, sort_keys=True)
    with (project_path / "english.lng").open("w", encoding="utf-8", newline="") as f:
        f.write(lng)


def parse_resx(file):
    namespace, _ = parse_resx_filename(file.name)
    with file.open("r", encoding="utf-8") as f:
        root = ElementTree.fromstring(f.read())
    lng = {}
    for data in root.iterfind("data"):
        name = data.attrib["name"]
        text = data.find("value").text
        text = convert_braces_to_percents(text)
        lng[f"{namespace}_{name}"] = text
    return lng


def generate_pot_file(project_path):
    english_file = project_path / "english.lng"
    if not file_updated(english_file):
        return
    with english_file.open("r") as f:
        lng = json.load(f)
    lng.pop("Culture")
    source = []
    for identifier, string in lng.items():
        source.append(f"# {identifier}")
        source.append(get_source_line_for_pot(convert_percents_to_braces(string)))
    source = "\n".join(source)
    source += "\n"
    pot = generate_pot_file_from_source(source, project_path.name)
    with (project_path / (project_path.name + ".pot")).open(
        "w", encoding="utf-8", newline=""
    ) as f:
        f.write(pot)


def get_source_line_for_pot(string):
    quote = None
    for q in ['"', "'", '"""', "'''"]:
        if q not in string:
            quote = q
            break
    if quote is None:
        raise RuntimeError(f"Failed to find quotes for string {string[:200]}")
    return f"_({quote}{string}{quote})"


def generate_pot_file_from_source(source, package_name):
    process = subprocess.Popen(
        [
            "xgettext",
            "-o",
            "-",
            "--language=Python",
            "-c",
            "--no-location",
            "--add-comments",
            f"--msgid-bugs-address={EMAIL_ADDRESS}",
            f"--package-name={package_name}",
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    process.stdin.write(source.encode())
    process.stdin.flush()
    process.stdin.close()  # EOF
    pot = b""
    while process.poll() is None:
        pot += process.stdout.read()
    if process.returncode != 0:
        raise RuntimeError(f"xgettext failed with code {process.returncode}")
    return pot.decode()


def main():
    with (REPOSITORY_DIR / "projects.txt").open("r", encoding="utf-8") as f:
        project_dirs = [i for i in f.read().split("\n") if i]
    for project_dir in project_dirs:
        process_project(PROJECTS_DIR / project_dir)


if __name__ == "__main__":
    main()
