# Rôle `authentik`

Déploie Authentik (« Neutrinet ID ») en conteneurs Podman sur les VM `authentik`, avec toute la configuration de base en blueprints : groupes, politiques, flows, stages, mapping de groupes, notifications, brand. Les applications et les providers restent gérés à la main.

## Vérifier une modification

- Blueprints, sans VM, à lancer à la main avant chaque commit qui touche le rôle (aucun hook ni CI ne le fait), depuis la racine du dépôt :

  ```
  AUTHENTIK_SRC=<clone git d'Authentik> .venv/bin/python roles/authentik/molecule/default/check_blueprints.py
  AUTHENTIK_SRC=<clone git d'Authentik> .venv/bin/python -m pytest roles/authentik/molecule/default/test_check_blueprints.py
  ```

  Le script rend les blueprints, les valide contre le schéma de la version déployée et applique les garde-fous du rôle. Sans `AUTHENTIK_SRC` ni fichier de schéma en argument, il lance les garde-fous qui n'ont pas besoin du schéma et signale que le contrôle du schéma est sauté ; les tests qui demandent le schéma sont alors sautés.
- Instance de test : scénario molecule `molecule/default/` (vagrant, libvirt).
- Commandes et prérequis : [`molecule/default/INSTALL.rst`](molecule/default/INSTALL.rst).
