"""Tests de non-régression des garde-fous de `check_blueprints.py` (sans VM).

Lancement : `.venv/bin/python -m pytest roles/authentik/molecule/default/test_check_blueprints.py` ; les tests qui
demandent le schéma d'Authentik sont sautés si AUTHENTIK_SRC ne désigne pas un clone git d'Authentik.
"""

import copy
import json
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


def test_arbre_actuel_sans_erreur_hors_schema(files):
    assert cb.run_checks(files, ROLE_VARS) == []


def test_arbre_actuel_conforme_au_schema(files, schema):
    assert cb.check_schema(files, schema) + cb.check_attributes(files, schema) == []


def test_main_sans_schema(monkeypatch, capsys):
    monkeypatch.delenv("AUTHENTIK_SRC", raising=False)
    assert cb.main(["check_blueprints.py"]) == 0
    out = capsys.readouterr().out
    assert "CONTRÔLE DU SCHÉMA SAUTÉ" in out
    assert "ERREUR" not in out


def test_main_sans_schema_controle_en_echec(monkeypatch, capsys):
    monkeypatch.delenv("AUTHENTIK_SRC", raising=False)
    monkeypatch.setattr(cb, "check_i18n", lambda role_vars: ["traduction absente"])
    assert cb.main(["check_blueprints.py"]) == 1
    assert "ERREUR traduction absente" in capsys.readouterr().out


def test_main_avec_schema(schema, capsys):
    assert cb.main(["check_blueprints.py"]) == 0
    out = capsys.readouterr().out
    assert "rendu et schéma OK" in out and "SAUTÉ" not in out


def test_main_source_introuvable(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTHENTIK_SRC", str(tmp_path / "absent"))
    assert cb.main(["check_blueprints.py"]) == 2


def test_main_schema_en_argument_introuvable(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("AUTHENTIK_SRC", raising=False)
    absent = tmp_path / "absent.json"
    assert cb.main(["check_blueprints.py", str(absent)]) == 2
    assert f"schéma illisible ou introuvable : {absent}" in capsys.readouterr().out


def test_main_schema_d_une_autre_version_refuse(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("AUTHENTIK_SRC", raising=False)
    other = tmp_path / "schema.json"
    other.write_text(json.dumps({"title": "authentik 2025.10.1 Blueprint schema", "type": "object"}))
    assert cb.main(["check_blueprints.py", str(other)]) == 1
    assert f"la version déployée est {VERSION}" in capsys.readouterr().out


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


def copies(files):
    return {
        label: sum(len(pattern.findall(expression)) for _where, expression in cb.expressions(files))
        for label, pattern in cb.COPIED_BLOCKS.items()
    }


def test_bloc_recopie_present_partout(files):
    expected = cb.expected_copies(files)
    assert all(count > 0 for count in expected.values())
    assert copies(files) == expected


@pytest.mark.parametrize("template,name,label,old,new", [
    ("policies.yaml.j2", "neutrinet-email-verified", "détection de la langue",
     'plan = request.context.get("flow_plan")\n', 'plan = request.context.get("flow_plan") \n'),
    ("policies.yaml.j2", "neutrinet-email-verified", "détection de la langue",
     'plan.context["neutrinet_language"] = language\n', 'plan.context["neutrinet_language"] = language or "en"\n'),
    ("policies.yaml.j2", "neutrinet-reputation-reset", "réseau de la réputation",
     "address = ipaddress.ip_address(ClientIPMiddleware.get_client_ip(request.http_request))\n",
     "address = ipaddress.ip_address(ClientIPMiddleware.get_client_ip(request.http_request)) \n"),
    ("policies.yaml.j2", "neutrinet-reputation-reset", "réseau de la réputation",
     'in_network = {"where"', 'in_network = dict(**{"where"'),
    ("notifications.yaml.j2", "neutrinet-notify-security", "langue du destinataire",
     'recipient_language = (recipient.locale() or "")', 'recipient_language = (recipient.locale() or "en")'),
    ("notifications.yaml.j2", "neutrinet-notify-security", "langue du destinataire",
     'recipient_language = "en"\n', 'recipient_language = "en" \n'),
])
def test_bloc_recopie_premiere_ou_derniere_ligne_modifiee(files, template, name, label, old, new):
    attrs = entry(files, template, name, "authentik_policies_expression.expressionpolicy")["attrs"]
    assert attrs["expression"].count(old) == 1
    attrs["expression"] = attrs["expression"].replace(old, new)
    errors = cb.check_copies(files)
    assert len(errors) == 1 and name in errors[0] and label in errors[0]
    assert copies(files)[label] == cb.expected_copies(files)[label] - 1


def test_failure_result_absent(files):
    binding = next(
        item for item in files["flow-recovery.yaml.j2"][0]["entries"]
        if item["model"] == "authentik_policies.policybinding"
        and item["identifiers"]["policy"].suffix == "Find"
        and item["identifiers"]["policy"].value[1][1] == "neutrinet-email-link-missing"
    )
    del binding["attrs"]["failure_result"]
    errors = cb.check_failure_result(files)
    assert len(errors) == 1 and "neutrinet-email-link-missing" in errors[0]


def test_failure_result_vrai_refuse(files):
    binding = next(
        item for item in files["flow-authentication.yaml.j2"][0]["entries"]
        if item["model"] == "authentik_policies.policybinding"
        and item["identifiers"]["policy"].suffix == "Find"
        and item["identifiers"]["policy"].value[1][1] == "neutrinet-password-unchanged"
    )
    binding["attrs"] = {"failure_result": True}
    errors = cb.check_failure_result(files)
    assert len(errors) == 1 and "neutrinet-password-unchanged avec failure_result: true" in errors[0]


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
    witness = entry(files, "policies.yaml.j2", "neutrinet-password-unchanged")
    entries.remove(witness)
    entries.insert(0, witness)
    errors = cb.check_witnesses(files)
    assert len(errors) == 1 and "après le témoin neutrinet-password-unchanged" in errors[0]


def test_reference_sans_dependance(files):
    entries = files["flow-ldap.yaml.j2"][0]["entries"]
    entries[:] = [item for item in entries if item["model"] != "authentik_blueprints.metaapplyblueprint"]
    errors = cb.check_witnesses(files)
    assert any(error.startswith("flow-ldap.yaml.j2: référence") and "policies.yaml.j2" in error for error in errors)
    assert any(error.startswith("flow-ldap.yaml.j2: référence") and "stages.yaml.j2" in error for error in errors)
