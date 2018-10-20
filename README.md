# Infra for neutrinet

`virtualenv env`

`env/bin/pip install -r requirements.txt`


`env/bin/ansible-playbook playbook-infra/commun.yml`

playbook-infra = installation des programmes, serveurs et des VMS (config standard mais pas spécifique - exemple, install de nginx + config générique mais pas des vhosts)
playbook-apps = configuration des applications (ex config ispng, install mamboa, sensu,...)
playbook-web = service web, similaire à apps, mais à part car il y a plein


