# Filtres et communautés

Sources : `templates/bird/conf.d/10_bgp_filters_hygiene.conf.j2` pour les listes et les fonctions de rejet communes,
`templates/bird/conf.d/10_bgp_filters_policy.conf.j2` pour la politique (RTBH, communautés, local preference, import et export par type de
session). La table complète des valeurs de communautés est déployée sur chaque routeur dans `/etc/bird/community.md` (source :
`templates/bird/community.md.j2`) ; cette page décrit le mécanisme.

## Communautés internes

Les communautés larges `my_asn:0:X` portent l'état d'une route à l'intérieur de l'AS. Elles sont retirées à l'import de toute session externe et à
l'export vers toute session externe.

| Communauté | Fonction de test | Sens |
| --- | --- | --- |
| `my_asn:0:20` | `bgp_learned_by_ebgp()` | Route apprise d'un transitaire, d'un route-server ou d'un peering |
| `my_asn:0:30` | `bgp_learned_by_client()` | Route d'un client eBGP, ou l'un de nos agrégats (statique sur les cores) : candidate à l'export externe |
| `my_asn:0:40` | `bgp_is_own_network()` | Nos réseaux internes : réseaux connectés compris dans nos préfixes, `bird_internal_service_routes`, client iBGP |
| `my_asn:0:60` | `bgp_is_bogon_blackhole()` | Bogon Team Cymru, installé en blackhole et jamais exporté hors de l'AS |

## Fonctions de rejet communes

Les listes de référence sont définies dans `10_bgp_filters_hygiene.conf.j2` :

- `NEUTRINET_PREFIXES_V4` (80.67.181.0/24+, 80.67.191.0/24+) et `NEUTRINET_PREFIXES_V6` (2001:913:1000::/36+) : nos préfixes ;
- `BOGON_PREFIXES_V4` et `BOGON_PREFIXES_V6` : espaces réservés, dont 192.0.0.0/24, 3fff::/20 et 5f00::/16 ;
- `IXP_LAN_PREFIXES_V4` et `IXP_LAN_PREFIXES_V6` : réseaux d'interconnexion de BelgiumIX, BNIX et NL-ix ;
- `BOGON_ASNS` et `PRIVATE_ASNS` : ASN réservés et privés ;
- `TIER1_ASNS` : 174, 701, 1299, 2914, 3257, 3320, 3356, 3491, 4134, 5511, 6453, 6461, 6762, 6830, 7018 et 12956.

`bgp_import_reject_v4/v6` enchaîne les contrôles suivants à l'import d'un transitaire, d'un route-server, d'un peering ou d'un client à
prefix-list dynamique :

```mermaid
flowchart TB
    A["reject_bogon_asns : ASN réservé ou privé dans le chemin"] --> B["reject_long_aspaths : chemin de plus de 100 ASN"]
    B --> C["reject_too_many_communities : plus de 100 communautés, tous types confondus"]
    C --> D["reject_v4/v6_default_route"]
    D --> E["reject_v4/v6_short_prefixes : moins de /8 en IPv4, moins de /16 en IPv6"]
    E --> F["reject_v6_not_global_unicast : IPv6 hors 2000::/3"]
    F --> G["reject_v4/v6_bogon_prefixes"]
    G --> H["reject_v4/v6_ixp_lan_prefixes"]
    H --> I["reject_v4/v6_own_prefixes : nos propres préfixes"]
    I --> J["reject_v4/v6_small_prefixes : plus long que /24 en IPv4, que /48 en IPv6"]
    J --> K["reject_v4/v6_invalid_rpki : ROA invalide"]
    K --> L["reject_invalid_aspa : ASPA invalide"]
```

Le rejet de nos propres préfixes refuse un détournement de notre espace même si les caches RPKI sont indisponibles.

`bgp_export_reject_v4/v6` reprend à l'export l'ASN réservé, le chemin trop long, la route par défaut, les préfixes trop courts, l'IPv6 hors
2000::/3, les bogons, les préfixes trop longs et le RPKI. Pour une route à chemin vide (nos agrégats), le RPKI est vérifié avec notre ASN comme
origine.

Un client dont la prefix-list est écrite à la main (`irr_static_v4/v6`) passe par `bgp_import_reject_static_client_v4/v6` à la place : chemin
trop long, trop de communautés, route par défaut, RPKI si l'ASN d'origine est public, et ASPA. La prefix-list statique est alors la frontière de
confiance, ce qui permet à un client à ASN privé d'annoncer de l'espace CGNAT ou des routes de CPE plus longues que /24 ou /48 à l'intérieur de nos
préfixes.

ASPA : `reject_invalid_aspa` applique `aspa_check_downstream` à un transitaire et `aspa_check_upstream` à un peering, un route-server ou un
client. Une route à chemin vide n'est pas vérifiée.

## Import depuis l'extérieur

```mermaid
flowchart TB
    S[route reçue] --> CL["retrait des communautés my_asn:*:*<br/>et de 65535:666 (sauf client)"]
    CL --> NH{"peering : next hop = voisin ?"}
    NH -- non --> X[route rejetée]
    NH -- oui --> RT{"client : demande RTBH valide ?"}
    RT -- oui --> BH["dest = RTD_BLACKHOLE, local_pref = 900"]
    RT -- non --> RJ["fonctions de rejet"]
    BH --> IRR
    RJ -- rejet --> X
    RJ -- accepté --> IRR{"peering, client : préfixe dans irr_v4/v6 ?<br/>peering, route-server, client : pas de tier 1 ?"}
    IRR -- non --> X
    IRR -- oui --> TAG["marquage my_asn:&lt;asn&gt;:&lt;code&gt;"]
    TAG --> LP["local preference (bgp_local_pref_calcul, local_pref d'un transitaire)<br/>puis GRACEFUL_SHUTDOWN : 0"]
    LP --> SRC["my_asn:0:20 (externe), my_asn:0:30 (client eBGP) ou my_asn:0:40 (client iBGP)"]
```

Détails par type :

- `transit`, `route-server` et `peering` retirent la communauté `65535:666` reçue : seuls les clients peuvent demander un RTBH.
- `peering` rejette toute route dont le next hop n'est pas l'adresse du voisin, puis vérifie l'inclusion dans `irr_<slug>_v4/v6`.
- `peering`, `route-server` et `client` rejettent tout chemin qui contient un ASN tier 1. Pour un client, ce contrôle passe en premier, avant même
  la demande de RTBH.
- `client` vérifie toujours l'inclusion dans sa prefix-list IRR, y compris pour une demande de RTBH. Les fonctions de rejet sont sautées pour un
  RTBH valide, et la local preference reste alors à 900.
- La communauté GRACEFUL_SHUTDOWN (`65535:0`) met la local preference à 0 (`bgp_apply_graceful_shutdown`).

## Export vers l'extérieur

```mermaid
flowchart TB
    E{"my_asn:0:20 présente ?"} -- oui --> X[non exportée]
    E -- non --> G{"my_asn:0:30, my_asn:0:40<br/>ou 65535:666 présente ?"}
    G -- non --> X
    G -- oui --> HE{"peering vers AS 6939<br/>et route de NS-Global ?"}
    HE -- oui --> X
    HE -- non --> RT{"RTBH traduit pour cet ASN ?"}
    RT -- oui --> TR["communauté RTBH du voisin<br/>(+ NO_EXPORT vers un transitaire),<br/>ASN privés retirés du chemin,<br/>contrôle ASN réservé et bogon"]
    RT -- non --> RJ["bgp_export_reject_v4/v6"]
    TR -- rejet --> X
    RJ -- rejet --> X
    TR -- accepté --> OUT["retrait de my_asn:0:*, marquage my_asn:&lt;asn&gt;:&lt;code&gt;"]
    RJ -- accepté --> OUT
    OUT --> OK[exportée]
```

Une route apprise en eBGP n'est donc jamais réannoncée à un autre voisin externe, même si elle porte par ailleurs une communauté autorisée.

Particularités par type :

- `transit` : avec `prepend`, notre ASN est ajouté une à trois fois devant nos propres routes (chemin vide).
- `route-server` : ajoute `0:6939` aux routes de NS-Global (AS 398987, reconnues par `my_asn:398987:*`) et `<rs-asn>:0:<transit-asn>` pour
  chaque ASN de `bird_transit_asns`, afin que le route-server n'annonce pas nos routes à nos propres transitaires qui en seraient membres.
- `peering` : vers AS 6939 (Hurricane Electric), les routes de NS-Global sont refusées avant tout autre contrôle ; c'est l'équivalent, en session
  directe, du signal `0:6939` envoyé aux route-servers.
- `client` : seule la route par défaut est exportée, sans autre logique.

## RTBH (blackhole déclenché à distance)

```mermaid
sequenceDiagram
    participant Client
    participant Access as access (import)
    participant Core as core (rr client)
    participant Border as border
    participant Ext as transitaire / route-server / peering

    Client->>Access: route marquée 65535:666 (RFC 7999), /32 ou /128
    Access->>Access: match_rtbh_v4/v6 à l'import<br/>dest = RTD_BLACKHOLE, local_pref = 900, my_asn:0:30
    Access->>Core: relayée en iBGP
    Core->>Core: bgp_import_access_to_core : blackhole
    Core->>Border: relayée en iBGP (rr client)
    Border->>Border: bgp_import_core_to_border : blackhole
    Border->>Ext: match_rtbh_v4/v6 à l'export<br/>65535:666 traduite vers la communauté du voisin, NO_EXPORT vers un transitaire
```

Une demande RTBH sur un préfixe plus court que /32 ou /128 n'est pas un blackhole : la communauté `65535:666` est retirée et la route suit le
traitement normal.

À l'export, `match_rtbh_v4/v6` remplace `65535:666` par la communauté RTBH du voisin. Vers un transitaire seulement, il ajoute `NO_EXPORT`
(`65535:65281`) : un route-server qui respecte RFC 1997 ne redistribuerait pas une route marquée `NO_EXPORT` à ses membres. Les ASN privés sont
retirés du chemin, puis seuls les contrôles d'ASN réservé et de bogon s'appliquent (un /32 échouerait au contrôle de longueur). Si l'ASN du voisin
n'a pas de traduction, la communauté est retirée et la route passe par les contrôles normaux, qui la rejettent puisqu'elle est trop longue.

La table de traduction par ASN de destination se trouve dans `/etc/bird/community.md`.
