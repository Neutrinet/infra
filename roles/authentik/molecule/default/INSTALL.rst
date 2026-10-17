*********************************
Vagrant driver installation guide
*********************************

Requirements
============

* Vagrant
* libvirt, avec le plugin ``vagrant-libvirt`` (driver ``libvirt`` de ``molecule.yml``)

Install
=======

Please refer to the `Virtual environment`_ documentation for installation best
practices. If not using a virtual environment, please consider passing the
widely recommended `'--user' flag`_ when invoking ``pip``.

.. _Virtual environment: https://virtualenv.pypa.io/en/latest/
.. _'--user' flag: https://packaging.python.org/tutorials/installing-packages/#installing-to-the-user-site

.. code-block:: bash

    $ pip install 'molecule_vagrant'

Contrôle des blueprints
=======================

Contrôle des blueprints, sans VM (rendu, schéma de la version déployée,
garde-fous du rôle), puis tests de non-régression de ces garde-fous.
``AUTHENTIK_SRC`` désigne un clone git d'Authentik qui contient le tag
``version/<authentik_version>`` ; à défaut, passer le chemin d'un
``schema.json`` en argument :

.. code-block:: bash

    $ AUTHENTIK_SRC=<clone> .venv/bin/python roles/authentik/molecule/default/check_blueprints.py
    $ AUTHENTIK_SRC=<clone> .venv/bin/python -m pytest roles/authentik/molecule/default/test_check_blueprints.py
