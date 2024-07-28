import json
import os
import subprocess
from gettext import GNUTranslations
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from constants import LNG_FILE_REGEX, PO_FILE_REGEX
from language_manager import language_manager
from message_manager import message_manager
from utils import (
    convert_braces_to_percents,
    convert_percents_to_braces,
    get_percent_placeholders,
    parse_resx_filename,
)

REPOSITORY_DIR = Path(".")
PROJECTS_DIR = Path(os.environ["PROJECTS_DIR"])


def process_project(project_path):
    process_po_files(project_path)
    process_lng_files(project_path)
    generate_resx_files(project_path)


def get_english_lng(project_path):
    with (REPOSITORY_DIR / project_path.name / "english.lng").open(
        "r", encoding="utf-8"
    ) as f:
        english_lng = json.load(f)
    english_lng.pop("Culture")
    english_lng.pop("Language")
    return english_lng


def process_po_files(project_path):
    english_lng = get_english_lng(project_path)
    valid_po_files = []
    errors = []
    for file in project_path.glob("*.po"):
        if not PO_FILE_REGEX.match(file.name):
            errors.append(f"PO file {file} have incorrect name.")
            continue
        language_code = file.name.split(".")[0]
        if not (language_name := language_manager.get_language_name(language_code)):
            errors.append(
                f"PO file {file} have incorrect name. ISO 639-1 code is unknown"
            )
            continue
        valid_po_files.append((file, language_code, language_name))
    if errors:
        message_manager.add_list_message("Invalid PO files found", errors)
    for file, language_code, language_name in valid_po_files:
        process_po_file(
            project_path=project_path,
            english_lng=english_lng,
            file=file,
            language_code=language_code,
            language_name=language_name,
        )


def convert_po_to_mo(file):
    process = subprocess.Popen(
        ["msgfmt", "-o", "-", str(file)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    mo = b""
    while process.poll() is None:
        mo += process.stdout.read()
    if process.returncode != 0:
        raise RuntimeError(f"msgfmt failed with code {process.returncode}")
    return mo


def process_po_file(*, project_path, english_lng, file, language_code, language_name):
    mo_file = BytesIO(convert_po_to_mo(file))
    po_translation = GNUTranslations(mo_file)
    missing_strings = []
    lng = {"Culture": language_code, "Language": language_name.lower()}
    for identifier, string in english_lng.items():
        translated_string = po_translation._catalog.get(
            convert_percents_to_braces(string), None
        )
        if translated_string is None:
            missing_strings.append(f"{identifier} - {string[:200]}")
            continue
        lng[identifier] = convert_braces_to_percents(translated_string)
    if (total_missing := len(missing_strings)) > 50:
        del missing_strings[50:]
        missing_strings.append(f"{total_missing} more...")
    if missing_strings:
        message_manager.add_list_message(
            f"Missing strings in {project_path.name}/{file.name} PO translation",
            missing_strings,
        )
    with (project_path / (language_name.lower() + ".lng")).open(
        "w", encoding="utf-8", newline=""
    ) as f:
        json.dump(lng, f, ensure_ascii=False, indent=2, sort_keys=True)


def process_lng_files(project_path):
    english_lng = get_english_lng(project_path)
    valid_lng_files = []
    errors = []
    for file in project_path.glob("*.lng"):
        if not LNG_FILE_REGEX.match(file.name):
            errors.append(f"lng file {file} have incorrect name.")
            continue
        language_name = file.name.split(".")[0]
        if not (language_code := language_manager.get_language_code(language_name)):
            errors.append(
                f"lng file {file} have incorrect name. Failed to detect ISO 639-1 code"
            )
            continue
        valid_lng_files.append((file, language_code, language_name))
    if errors:
        message_manager.add_list_message("Invalid lng files found", errors)
    for file, language_code, language_name in valid_lng_files:
        process_lng_file(
            project_path=project_path,
            english_lng=english_lng,
            file=file,
            language_code=language_code,
            language_name=language_name,
        )


def process_lng_file(*, project_path, english_lng, file, language_code, language_name):
    with file.open("r", encoding="utf-8") as f:
        lng = json.load(f)
    errors = []
    missing = object()
    for key, required_value in [
        ("Culture", language_code),
        ("Language", language_name),
    ]:
        lng_value = lng.get(key, missing)
        if lng_value is missing:
            errors.append(f"{key} key is missing")
        elif lng_value != required_value:
            errors.append(
                f"{key} key value is incorrect. Required: {required_value}, Actual: {str(lng_value)[:200]}"
            )
    missing_strings = []
    placeholder_errors = []
    for identifier, string in english_lng.items():
        if identifier not in lng:
            missing_strings.append(f"{identifier} - {string[:200]}")
            continue
        placeholder_errors.extend(
            identifier + " - " + i
            for i in validate_placeholders(english_lng[identifier], lng[identifier])
        )
    if missing_strings:
        message_manager.add_list_message(
            f"Missing strings in {project_path.name}/{file.name} lng translation",
            missing_strings,
        )
    if placeholder_errors:
        message_manager.add_list_message(
            f"Placeholder errors in {project_path.name}/{file.name} lng translation",
            placeholder_errors,
        )


def validate_placeholders(original_string, translated_string):
    original_placeholders = get_percent_placeholders(original_string)
    translated_placeholders = get_percent_placeholders(translated_string)
    errors = []
    for p in original_placeholders:
        if (count := translated_placeholders.count(p)) == 1:
            continue
        if count == 0:
            errors.append(f"Placeholder %{p} not found")
        else:
            errors.append(f"Placeholder %{p} duplicated")
    for p in translated_placeholders:
        if p not in original_placeholders:
            errors.append(f"Extra placeholder %{p} found in translated string")
    return errors


def generate_resx_files(project_path):
    resx_files = []
    for file in project_path.glob("*.resx"):
        if parse_resx_filename(file.name)[1] is None:
            resx_files.append(file)
    for lng_file in project_path.glob("*.lng"):
        if lng_file.name == "english.lng":
            continue
        with lng_file.open("r", encoding="utf-8") as f:
            lng = json.load(f)
        errors = []
        for resx_file in resx_files:
            errors.extend(generate_resx_from_lng(lng, resx_file))
        if errors:
            message_manager.add_list_message(
                f"Errors when generating resx from {project_path.name}/{lng_file.name}",
                errors,
            )


def generate_resx_from_lng(lng, resx_file):
    namespace, _ = parse_resx_filename(resx_file.name)
    with resx_file.open("r", encoding="utf-8") as f:
        root = ElementTree.fromstring(f.read())
    errors = []
    for data in root.iterfind("data"):
        name = data.attrib["name"]
        value = data.find("value")
        identifier = namespace + "_" + name
        if identifier not in lng:
            errors.append(f"Key {identifier} not found")
            continue
        value.text = convert_percents_to_braces(lng[identifier])
    with resx_file.with_name(f'{namespace}.{lng['Culture']}.resx').open("wb") as f:
        f.write(ElementTree.tostring(root, encoding="utf-8"))
    return errors


def main():
    language_manager.initialize(REPOSITORY_DIR / "languages.json")
    with (REPOSITORY_DIR / "projects.txt").open("r", encoding="utf-8") as f:
        project_dirs = [i for i in f.read().split("\n") if i]
    for project_dir in project_dirs:
        process_project(PROJECTS_DIR / project_dir)
        messages = message_manager.get_messages()
        if not messages:
            messages = [
                "Validation and conversion completed without errors, let's wait for the review team.\n"
                "Thanks for your contribution!"
            ]
        with (REPOSITORY_DIR / "result.txt").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            f.write("\n".join(messages))


if __name__ == "__main__":
    main()
