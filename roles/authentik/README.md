# Rôle `authentik`

Déploie Authentik (« Neutrinet ID ») en conteneurs Podman sur les VM `authentik`, avec toute la configuration de base en blueprints : groupes, politiques, flows, stages, mapping de groupes, notifications, brand. Les applications et les providers restent gérés à la main.

## Vérifier une modification

- Blueprints, sans VM : `molecule/default/check_blueprints.py` (rendu, schéma de la version déployée, garde-fous du rôle) et ses tests `molecule/default/test_check_blueprints.py`.
- Instance de test : scénario molecule `molecule/default/` (vagrant, libvirt).
- Commandes et prérequis : [`molecule/default/INSTALL.rst`](molecule/default/INSTALL.rst).
