# Infra for neutrinet

`virtualenv env`

`env/bin/pip install -r requirements.txt`


`env/bin/ansible-playbook playbook-infra/commun.yml`

playbook-infra = installation des programmes, serveurs et des VMS (config standard mais pas spécifique - exemple, install de nginx + config générique mais pas des vhosts)
playbook-apps = configuration des applications (ex config ispng, install mamboa, sensu,...)
playbook-web = service web, similaire à apps, mais à part car il y a plein

## Tester l'infra en local

1. Démarrer la VM web via vagrant (son adresse IP est 192.168.33.10):

```
$ vagrant up
```

2. Tester la connection SSH et automatiquement ajouter l'hôte au fichier `.known_hosts`:

```
$ vagrant ssh
$ exit
```

3. Lancer la configuration/installation de la VM avec ansible:

```
$ ansible-playbook playbooks-infra/vagrant_web.yml
```

Remarques:

La première fois qu'ansible sera lancé, son exécution s'arrêtera sur:
`nginx-server : Activer le service nginx au démarage. Plantera la premiere fois car les params DH sont en cours de génération]`  
car la génération du certificat prend assez longtemps. Il ne faut pas relancer la commande ansible avant que la génération du certificat soit terminée. Pour s'en assurer, il suffit de se connecter à la VM en faisant `$ vagrant ssh` et une fois connecté, observer le processus `openssl`: `ps aux | grep openssl`. Attendre que celui-ci soit terminé, taper `$ exit` pour terminer la session SSH, puis relancer la commande ansible spécifiée au point `3.`.

4. Tester l'app Rails (pour l'instant, il n'y a pas de reverse proxy nginx):

```
$ vagrant ssh
$ curl http://localhost:3001
```

