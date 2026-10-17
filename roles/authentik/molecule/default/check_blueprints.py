#!/usr/bin/env python3
"""Rend les blueprints du rôle authentik et les valide contre le schéma officiel."""

import json
import re
import sys
from pathlib import Path

import jinja2
import jsonschema
import yaml

ROLE = Path(__file__).resolve().parents[2]
TEMPLATES = ROLE / "templates" / "blueprints"


class Loader(yaml.SafeLoader):
    """Chargeur YAML qui accepte les tags personnalisés d'Authentik."""


def tag_constructor(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    else:
        value = loader.construct_sequence(node, deep=True)
    loader.tags.append((suffix, value))
    if suffix == "Condition":
        return True
    return f"!{suffix}"


Loader.add_multi_constructor("!", tag_constructor)


def render(path, context):
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
    )
    env.filters["to_json"] = json.dumps
    env.filters["comment"] = lambda text: "\n".join(f"# {line}" for line in text.splitlines())
    return env.from_string(path.read_text()).render(context)


def load(text):
    loader = Loader(text)
    loader.tags = []
    try:
        return loader.get_single_data(), loader.tags
    finally:
        loader.dispose()


def main():
    schema = json.loads(Path(sys.argv[1]).read_text())
    defaults = yaml.safe_load((ROLE / "defaults" / "main.yml").read_text())
    blocklist = sorted(
        {
            line
            for line in (ROLE / "files" / "username_blocklist.txt").read_text().splitlines()
            + defaults["authentik_username_blocklist"]
            if re.fullmatch(r"[a-z0-9_-]+", line)
        }
    )
    role_vars = yaml.safe_load((ROLE / "vars" / "main.yml").read_text())
    context = {
        **defaults,
        **role_vars,
        "ansible_managed": "Ansible managed",
        "_authentik_username_blocklist": blocklist,
    }

    templates = sorted(TEMPLATES.glob("*.yaml.j2"))
    if not templates:
        print("aucun blueprint trouvé")
        return 1

    errors = []
    names = set()
    finds = []
    for template in templates:
        data, tags = load(render(template, context))
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{template.name}: {exc.message} ({list(exc.absolute_path)})")
            continue
        ids = {entry["id"] for entry in data["entries"] if "id" in entry}
        for entry in data["entries"]:
            identifiers = entry.get("identifiers", {})
            for key in ("name", "slug"):
                if key in identifiers:
                    names.add(identifiers[key])
        for suffix, value in tags:
            if suffix == "KeyOf" and value not in ids:
                errors.append(f"{template.name}: !KeyOf {value} sans id correspondant")
            if suffix == "Find" and len(value) == 2 and isinstance(value[1], list) and len(value[1]) == 2:
                finds.append((template.name, value[1][1]))
        print(f"{template.name}: rendu et schéma OK")

    for name, target in finds:
        if str(target).startswith("neutrinet-") and target not in names:
            errors.append(f"{name}: !Find {target} introuvable dans les blueprints")

    for error in errors:
        print(f"ERREUR {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
