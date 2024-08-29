# generate CA



openssl ecparam -name secp384r1 -genkey -noout -out neutrinet-ca-dev.key
openssl req -x509 -new -key neutrinet-ca-dev.key -out neutrinet-ca-dev.crt -days 18250 -config ca.conf


trust anchor --store myCA.crt
