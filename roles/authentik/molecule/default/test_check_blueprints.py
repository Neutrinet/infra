"""Tests de non-régression des garde-fous de `check_blueprints.py` (sans VM).

Lancement : `.venv/bin/python -m pytest roles/authentik/molecule/default/test_check_blueprints.py` ; les tests qui
demandent le schéma d'Authentik sont sautés si AUTHENTIK_SRC ne désigne pas un clone git d'Authentik.
"""

import copy
import os

import pytest

import check_blueprints as cb

DEFAULTS, ROLE_VARS = cb.role_files()
VERSION = DEFAULTS["authentik_version"]


@pytest.fixture(scope="module")
def rendered():
    return cb.render_all(cb.build_context(DEFAULTS, ROLE_VARS))


@pytest.fixture
def files(rendered):
    return copy.deepcopy(rendered)


@pytest.fixture(scope="module")
def schema():
    if not os.environ.get("AUTHENTIK_SRC"):
        pytest.skip("AUTHENTIK_SRC non défini")
    loaded = cb.load_schema(["check_blueprints.py"], VERSION)
    if loaded is None:
        pytest.skip(f"schéma de la version {VERSION} introuvable")
    return loaded


def entry(files, template, name, model=None):
    for item in files[template][0]["entries"]:
        if cb.entry_name(item) == name and (model is None or item["model"] == model):
            return item
    raise AssertionError(f"{name} absent de {template}")


def test_schema_par_defaut_sans_source(monkeypatch, capsys):
    monkeypatch.delenv("AUTHENTIK_SRC", raising=False)
    assert cb.load_schema(["check_blueprints.py"], VERSION) is None
    assert f"version/{VERSION}" in capsys.readouterr().out


def test_arbre_actuel_sans_erreur(files, schema):
    errors = (
        cb.check_schema(files, schema)
        + cb.check_attributes(files, schema)
        + cb.check_references(files)
        + cb.check_binding_evaluation(files)
        + cb.check_orders(files)
        + cb.check_i18n(ROLE_VARS)
        + cb.check_copies(files)
        + cb.check_witnesses(files)
    )
    assert errors == []


def test_attribut_inconnu_refuse(files, schema):
    entry(files, "policies.yaml.j2", "neutrinet-is-privileged")["attrs"]["failure_result"] = True
    errors = cb.check_attributes(files, schema)
    assert len(errors) == 1 and "attrs.failure_result" in errors[0]


def test_traduction_manquante(files):
    role_vars = copy.deepcopy(ROLE_VARS)
    del role_vars["_authentik_i18n"]["msg_deny"]["de"]
    role_vars["_authentik_locale_tags"].pop("nl")
    errors = cb.check_i18n(role_vars)
    assert len(errors) == 2
    assert "msg_deny" in errors[0] and "_authentik_locale_tags" in errors[1]


@pytest.mark.parametrize("template,name,old,new", [
    ("policies.yaml.j2", "neutrinet-username", 'language = "en"', 'language = "fr"'),
    ("policies.yaml.j2", "neutrinet-reputation-reset", "/64", "/56"),
    ("notifications.yaml.j2", "neutrinet-notify-security", 'not in ["en", "fr", "nl", "de"]', 'not in ["en", "fr"]'),
])
def test_bloc_recopie_divergent(files, template, name, old, new):
    attrs = entry(files, template, name, "authentik_policies_expression.expressionpolicy")["attrs"]
    assert old in attrs["expression"]
    attrs["expression"] = attrs["expression"].replace(old, new, 1)
    errors = cb.check_copies(files)
    assert len(errors) == 1 and name in errors[0]


def test_bloc_recopie_present_partout(files):
    counts = {label: 0 for label in cb.COPIED_BLOCKS}
    for data, _tags in files.values():
        for item in data["entries"]:
            expression = (item.get("attrs") or {}).get("expression", "")
            for label, pattern in cb.COPIED_BLOCKS.items():
                counts[label] += len(pattern.findall(expression))
    assert counts["détection de la langue"] >= 12
    assert counts["réseau de la réputation"] == 2
    assert counts["langue du destinataire"] == 2


def test_ordre_partage(files):
    bindings = [
        item for item in files["flow-recovery.yaml.j2"][0]["entries"]
        if item["model"] == "authentik_flows.flowstagebinding"
    ]
    bindings[1]["identifiers"]["order"] = bindings[0]["identifiers"]["order"]
    errors = cb.check_orders(files)
    assert len(errors) == 1 and "flow-recovery.yaml.j2" in errors[0]


def test_liaison_sans_evaluation(files):
    binding = next(
        item for item in files["flow-ldap.yaml.j2"][0]["entries"]
        if item["model"] == "authentik_flows.flowstagebinding"
    )
    binding["attrs"].update(evaluate_on_plan=False, re_evaluate_policies=False)
    assert len(cb.check_binding_evaluation(files)) == 1


def test_keyof_et_find_inconnus(files):
    data, tags = files["flow-ldap.yaml.j2"]
    tags.append(("KeyOf", "absent"))
    tags.append(("Find", ["authentik_flows.flow", ["slug", "neutrinet-absent"]]))
    assert len(cb.check_references(files)) == 2


def condition(model, witness):
    return cb.Tag("Condition", ["NOR", cb.Tag("Find", [model, ["name", witness]])])


def test_temoin_absent_de_la_cible(files):
    dependency = files["flow-ldap.yaml.j2"][0]["entries"][0]
    dependency["conditions"] = [condition("authentik_policies_expression.expressionpolicy", "neutrinet-absent")]
    errors = cb.check_witnesses(files)
    assert any("témoin neutrinet-absent absent" in error for error in errors)
    assert any("plusieurs témoins" in error for error in errors)


def test_reference_placee_apres_le_temoin(files):
    entries = files["policies.yaml.j2"][0]["entries"]
    witness = entry(files, "policies.yaml.j2", "neutrinet-terminate-sessions")
    entries.remove(witness)
    entries.insert(0, witness)
    errors = cb.check_witnesses(files)
    assert len(errors) == 1 and "après le témoin neutrinet-terminate-sessions" in errors[0]


def test_reference_sans_dependance(files):
    entries = files["flow-ldap.yaml.j2"][0]["entries"]
    entries[:] = [item for item in entries if item["model"] != "authentik_blueprints.metaapplyblueprint"]
    errors = cb.check_witnesses(files)
    assert any(error.startswith("flow-ldap.yaml.j2: référence") and "policies.yaml.j2" in error for error in errors)
    assert any(error.startswith("flow-ldap.yaml.j2: référence") and "stages.yaml.j2" in error for error in errors)
