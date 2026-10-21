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
