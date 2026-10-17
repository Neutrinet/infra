#!/usr/bin/env python3
"""Rend les blueprints du rôle authentik, les valide contre le schéma d'Authentik et applique les garde-fous du rôle.

Usage : check_blueprints.py [schema.json]

Sans argument, le schéma est lu dans le clone git d'Authentik désigné par la variable d'environnement
AUTHENTIK_SRC, au tag de la version déployée (`authentik_version` de `defaults/main.yml`). Sans argument ni
AUTHENTIK_SRC, les contrôles qui n'ont pas besoin du schéma sont lancés et le contrôle du schéma est signalé
comme sauté. Code de sortie : 0 si tous les contrôles lancés passent, 1 si un contrôle échoue, 2 si le schéma
demandé (argument ou AUTHENTIK_SRC) est introuvable.
"""

import collections
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import jinja2
import jsonschema
import yaml

ROLE = Path(__file__).resolve().parents[2]
TEMPLATES = ROLE / "templates" / "blueprints"

LANGUAGE_BLOCK = re.compile(
    r'plan = request\.context\.get\("flow_plan"\)\n.*?plan\.context\["neutrinet_language"\] = language\n', re.S
)
NETWORK_BLOCK = re.compile(
    r"address = ipaddress\.ip_address\(ClientIPMiddleware\.get_client_ip\(request\.http_request\)\)\n"
    r".*?in_network = \{[^\n]*\}\n",
    re.S,
)
RECIPIENT_BLOCK = re.compile(
    r'recipient_language = \(recipient\.locale\(\) or ""\)[^\n]*\n[^\n]*\n[^\n]*recipient_language = "en"\n'
)
COPIED_BLOCKS = {
    "détection de la langue": LANGUAGE_BLOCK,
    "réseau de la réputation": NETWORK_BLOCK,
    "langue du destinataire": RECIPIENT_BLOCK,
}
COPIED_MARKERS = {
    "détection de la langue": (
        'plan = request.context.get("flow_plan")\nif plan is None and request.http_request is not None:',
        'language = (language or "").replace("_", "-").split("-")[0].lower()',
        "neutrinet_language",
    ),
    "réseau de la réputation": (
        "ClientIPMiddleware.get_client_ip",
        "/64",
        "in_network = {",
    ),
    "langue du destinataire": (
        "recipient.locale()",
        'recipient_language = "en"',
    ),
}
FAILURE_RESULT_POLICIES = {
    "neutrinet-is-privileged",
    "neutrinet-reputation-ip",
    "neutrinet-red-admin-only",
    "neutrinet-red-invitation",
    "neutrinet-email-link-missing",
}


class Tag(str):
    """Valeur d'un tag personnalisé d'Authentik : se compare comme `!<tag>`, garde son argument."""

    def __new__(cls, suffix, value):
        tag = super().__new__(cls, f"!{suffix}")
        tag.suffix = suffix
        tag.value = value
        return tag

    def __reduce__(self):
        return (Tag, (self.suffix, self.value))

    def key(self):
        return (self.suffix, json.dumps(self.value, default=str))


class Loader(yaml.SafeLoader):
    """Chargeur YAML qui accepte les tags personnalisés d'Authentik."""


def tag_constructor(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    else:
        value = loader.construct_sequence(node, deep=True)
    loader.tags.append((suffix, value))
    return Tag(suffix, value)


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


def schema_view(data):
    """Copie des données telle que le schéma la voit : une `!Condition` y est un booléen."""
    view = copy.deepcopy(data)
    for entry in view.get("entries", []):
        if "conditions" in entry:
            entry["conditions"] = [True for _condition in entry["conditions"]]
    return view


def role_files():
    defaults = yaml.safe_load((ROLE / "defaults" / "main.yml").read_text())
    role_vars = yaml.safe_load((ROLE / "vars" / "main.yml").read_text())
    return defaults, role_vars


def build_context(defaults, role_vars):
    blocklist = sorted(
        {
            line
            for line in (ROLE / "files" / "username_blocklist.txt").read_text().splitlines()
            + defaults["authentik_username_blocklist"]
            if re.fullmatch(r"[a-z0-9_-]+", line)
        }
    )
    return {
        **defaults,
        **role_vars,
        "ansible_managed": "Ansible managed",
        "_authentik_username_blocklist": blocklist,
    }


def render_all(context):
    """{nom du template: (données, tags)} pour chaque blueprint du rôle."""
    return {template.name: load(render(template, context)) for template in sorted(TEMPLATES.glob("*.yaml.j2"))}


def entry_name(entry):
    identifiers = entry.get("identifiers") or {}
    return identifiers.get("name", identifiers.get("slug"))


def is_find(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[1], list)
        and len(value[1]) == 2
    )


def check_schema(files, schema):
    errors = []
    for name, (data, _tags) in files.items():
        try:
            jsonschema.validate(schema_view(data), schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{name}: {exc.message} ({list(exc.absolute_path)})")
    return errors


def check_attributes(files, schema):
    """Chaque clé de `attrs` et `identifiers` existe dans la définition du modèle (le schéma ne l'impose pas)."""
    errors = []
    definitions = schema["definitions"]
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            definition = definitions.get(f"model_{entry['model']}")
            if definition is None:
                errors.append(f"{name}: modèle inconnu {entry['model']}")
                continue
            known = set(definition.get("properties", {}))
            for section in ("attrs", "identifiers"):
                for key in entry.get(section) or {}:
                    if key not in known and not (section == "identifiers" and key == "pk"):
                        errors.append(f"{name}: {entry['model']} {entry_name(entry)} : attribut inconnu {section}.{key}")
    return errors


def check_references(files):
    errors = []
    names = set()
    for data, _tags in files.values():
        for entry in data["entries"]:
            identifiers = entry.get("identifiers") or {}
            for key in ("name", "slug"):
                if key in identifiers:
                    names.add(identifiers[key])
    for name, (data, tags) in files.items():
        ids = {entry["id"] for entry in data["entries"] if "id" in entry}
        for suffix, value in tags:
            if suffix == "KeyOf" and value not in ids:
                errors.append(f"{name}: !KeyOf {value} sans id correspondant")
            if suffix == "Find" and is_find(value) and str(value[1][1]).startswith("neutrinet-") and value[1][1] not in names:
                errors.append(f"{name}: !Find {value[1][1]} introuvable dans les blueprints")
    return errors


def check_binding_evaluation(files):
    errors = []
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            attrs = entry.get("attrs") or {}
            if (
                entry["model"] == "authentik_flows.flowstagebinding"
                and not attrs.get("evaluate_on_plan", False)
                and not attrs.get("re_evaluate_policies", True)
            ):
                errors.append(f"{name}: liaison de stage sans evaluate_on_plan ni re_evaluate_policies")
    return errors


def check_orders(files):
    """Deux liaisons de stage d'un même flow n'ont jamais le même ordre."""
    errors = []
    seen = collections.defaultdict(list)
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            if entry["model"] != "authentik_flows.flowstagebinding":
                continue
            target = entry["identifiers"]["target"]
            flow = (name, target.key()) if target.suffix == "KeyOf" else target.key()
            seen[(flow, entry["identifiers"]["order"])].append(f"{name}:{entry['identifiers']['stage'].key()[1]}")
    for (flow, order), stages in seen.items():
        if len(stages) > 1:
            errors.append(f"ordre {order} partagé par plusieurs liaisons du même flow : {stages}")
    return errors


def check_i18n(role_vars):
    """Chaque table de traductions couvre exactement les langues du rôle."""
    errors = []
    languages = set(role_vars["_authentik_languages"])
    for key, table in role_vars["_authentik_i18n"].items():
        if set(table) != languages:
            errors.append(f"_authentik_i18n.{key} : langues {sorted(set(table))}, attendues {sorted(languages)}")
    if set(role_vars["_authentik_locale_tags"]) != languages:
        errors.append(f"_authentik_locale_tags : langues {sorted(role_vars['_authentik_locale_tags'])}, attendues {sorted(languages)}")
    return errors


def expressions(files):
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            expression = (entry.get("attrs") or {}).get("expression", "")
            if expression:
                yield f"{name}:{entry_name(entry)}", expression


def expected_copies(files):
    """{bloc: nombre d'expressions qui contiennent un de ses marqueurs}, soit le nombre de copies attendues."""
    return {
        label: sum(1 for _where, expression in expressions(files) if any(marker in expression for marker in markers))
        for label, markers in COPIED_MARKERS.items()
    }


def marker_positions(expression, marker):
    start = expression.find(marker)
    while start != -1:
        yield start
        start = expression.find(marker, start + 1)


def check_copies(files):
    """Les blocs recopiés d'une expression à l'autre restent complets et identiques.

    Toute expression qui contient un marqueur d'un bloc (début, fin ou ligne caractéristique) en contient une copie
    complète, et chaque occurrence d'un marqueur se trouve dans une copie complète ; toutes les copies sont identiques.
    """
    errors = []
    for label, pattern in COPIED_BLOCKS.items():
        variants = collections.defaultdict(list)
        for where, expression in expressions(files):
            spans = []
            for match in pattern.finditer(expression):
                variants[match.group(0)].append(where)
                spans.append(match.span())
            outside = [
                marker
                for marker in COPIED_MARKERS[label]
                for start in marker_positions(expression, marker)
                if not any(begin <= start and start + len(marker) <= end for begin, end in spans)
            ]
            if outside:
                errors.append(f"{where}: bloc « {label} » incomplet ou modifié (« {outside[0].splitlines()[0]} » hors d'une copie complète)")
        if len(variants) > 1:
            groups = sorted(variants.values(), key=len)
            errors.append(f"bloc « {label} » divergent : {groups[:-1]} diffèrent de {groups[-1][:3]}…")
    return errors


def check_failure_result(files):
    """Les liaisons des politiques de privilège et de refus ont `failure_result: true`."""
    errors = []
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            if entry["model"] != "authentik_policies.policybinding":
                continue
            policy = (entry.get("identifiers") or {}).get("policy")
            if not isinstance(policy, Tag) or policy.suffix != "Find" or not is_find(policy.value):
                continue
            if policy.value[1][1] in FAILURE_RESULT_POLICIES and (entry.get("attrs") or {}).get("failure_result") is not True:
                errors.append(f"{name}: liaison de {policy.value[1][1]} sans failure_result: true")
    return errors


def check_witnesses(files):
    """Dépendances conditionnelles entre blueprints Neutrinet.

    - le témoin d'une dépendance conditionnelle existe dans sa cible, avec le même modèle ;
    - toutes les dépendances vers une même cible utilisent le même témoin ;
    - aucun objet de la cible référencé par `!Find` depuis un autre fichier ne vient après le témoin ;
    - un fichier qui référence un objet d'un autre blueprint Neutrinet en dépend, directement ou par transitivité.
    """
    errors = []
    by_blueprint = {data["metadata"]["name"]: name for name, (data, _tags) in files.items()}
    owners = collections.defaultdict(set)
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            if entry_name(entry) is not None:
                owners[entry_name(entry)].add((name, entry["model"]))
    dependencies = collections.defaultdict(set)
    witnesses = collections.defaultdict(set)
    for name, (data, _tags) in files.items():
        for entry in data["entries"]:
            if entry["model"] != "authentik_blueprints.metaapplyblueprint":
                continue
            target = by_blueprint.get(entry["attrs"]["identifiers"]["name"])
            if target is None:
                continue
            dependencies[name].add(target)
            for condition in entry.get("conditions") or []:
                find = condition.value[1] if isinstance(condition, Tag) and condition.suffix == "Condition" else None
                if not isinstance(find, Tag) or find.suffix != "Find" or not is_find(find.value):
                    errors.append(f"{name}: dépendance vers {target} avec une condition non reconnue")
                    continue
                model, (_field, witness) = find.value
                witnesses[target].add(witness)
                if (target, model) not in owners.get(witness, set()):
                    errors.append(f"{name}: témoin {witness} absent de {target} (ou d'un autre modèle)")
    referenced = collections.defaultdict(set)
    references = collections.defaultdict(set)
    for name, (_data, tags) in files.items():
        for suffix, value in tags:
            if suffix != "Find" or not is_find(value):
                continue
            for owner, _model in owners.get(value[1][1], set()):
                if owner != name:
                    referenced[owner].add(value[1][1])
                    references[(name, owner)].add(value[1][1])
    for target, names in witnesses.items():
        if len(names) > 1:
            errors.append(f"{target}: plusieurs témoins {sorted(names)}")
        order = [entry_name(entry) for entry in files[target][0]["entries"]]
        for witness in names:
            if witness not in order:
                continue
            late = [ref for ref in referenced[target] if ref in order and order.index(ref) > order.index(witness)]
            if late:
                errors.append(f"{target}: {sorted(late)} référencé(s) ailleurs mais placé(s) après le témoin {witness}")

    def closure(name):
        seen, stack = set(), [name]
        while stack:
            for dependency in dependencies[stack.pop()]:
                if dependency not in seen:
                    seen.add(dependency)
                    stack.append(dependency)
        return seen

    for (name, owner), refs in references.items():
        if owner not in closure(name):
            errors.append(f"{name}: référence {sorted(refs)} de {owner} sans dépendance, même transitive")
    return errors


def schema_requested(argv):
    return len(argv) > 1 or bool(os.environ.get("AUTHENTIK_SRC"))


def load_schema(argv, version):
    if len(argv) > 1:
        return json.loads(Path(argv[1]).read_text())
    source = os.environ.get("AUTHENTIK_SRC")
    if source:
        result = subprocess.run(
            ["git", "-C", source, "show", f"version/{version}:blueprints/schema.json"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"schéma introuvable dans {source} au tag version/{version} : {result.stderr.strip()}")
        return None
    print_usage(argv, version)
    return None


def print_usage(argv, version):
    print(
        f"usage : {argv[0]} [schema.json]\n"
        f"Sans argument, AUTHENTIK_SRC doit désigner un clone git d'Authentik qui contient le tag version/{version}.\n"
        f"Schéma de la version déployée : https://raw.githubusercontent.com/goauthentik/authentik/version/{version}/blueprints/schema.json"
    )


def run_checks(files, role_vars, schema=None):
    """Erreurs de tous les contrôles ; sans schéma, ceux qui en ont besoin ne sont pas lancés."""
    errors = []
    if schema is not None:
        errors += check_schema(files, schema) + check_attributes(files, schema)
    return errors + (
        check_references(files)
        + check_binding_evaluation(files)
        + check_failure_result(files)
        + check_orders(files)
        + check_i18n(role_vars)
        + check_copies(files)
        + check_witnesses(files)
    )


def main(argv):
    defaults, role_vars = role_files()
    version = defaults["authentik_version"]
    schema = None
    if schema_requested(argv):
        schema = load_schema(argv, version)
        if schema is None:
            return 2
        title = schema.get("title", "")
        if f" {version} " not in f" {title} ":
            print(f"ERREUR schéma « {title} » : la version déployée est {version}")
            return 1

    files = render_all(build_context(defaults, role_vars))
    if not files:
        print("aucun blueprint trouvé")
        return 1
    errors = run_checks(files, role_vars, schema)
    status = "rendu et schéma OK" if schema is not None else "rendu OK"
    for name in files:
        if not any(error.startswith(f"{name}:") for error in errors):
            print(f"{name}: {status}")
    for error in errors:
        print(f"ERREUR {error}")
    if schema is None:
        print_usage(argv, version)
        print("CONTRÔLE DU SCHÉMA SAUTÉ (schéma et attributs des modèles) : aucun schéma donné.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
