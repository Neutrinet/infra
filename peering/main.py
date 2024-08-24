import requests
import time
from pprint import pprint
from collections import Counter
from slugify import slugify
import yaml


def make_request(url):
    api_key = ""
    headers = {"Authorization": "Api-Key " + api_key}

    try:
        response = requests.get(url=url, headers=headers)

        # Check the HTTP status code
        if response.status_code == 429:
            # Extract the retry delay from the Retry-After header
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                time.sleep(int(retry_after))
                return make_request(url)  # Retry after the delay
        elif response.status_code == 200:
            return response.json()  # Process the response if successful
        elif response.status_code == 404:
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


def is_asn_present(asn_to_check, peers):
    for peer in peers:
        if peer["asn"] == asn_to_check:
            return True
    return False


def get_last_segment_v6(ipv6_address):
    segments = ipv6_address.split(":")
    non_empty_segments = [segment for segment in segments if segment]
    last_segment = non_empty_segments[-1]
    return last_segment.zfill(2)


def get_last_segment_v4(ipv4_address):
    segments = ipv4_address.split(".")
    non_empty_segments = [segment for segment in segments if segment]
    last_segment = non_empty_segments[-1]
    return last_segment.zfill(2)


belgiumix_config_file = "inventories/host_vars/edge-nlix.louise.neutri.net.yml"

with open(belgiumix_config_file, "r") as file:
    belgiumix_config = yaml.safe_load(file)
    belgiumix_peers = belgiumix_config.get("bird_peers_upstreams", [])

r = make_request(url="https://www.peeringdb.com/api/netixlan?ix=64&depth=0")

all_peers_in_ix = r.get("data")

asn_list = [entry["asn"] for entry in all_peers_in_ix]
asn_count = Counter(asn_list)

duplicate_asns = [asn for asn, count in asn_count.items() if count > 1]

new_bird_peers_upstreams = []

for peer in all_peers_in_ix:
    if peer.get("asn") != 204059:

        peering_url_get_asn = (
            "https://www.peeringdb.com/api/net/{net_id}?depth=0".format(
                net_id=peer.get("net_id")
            )
        )
        peering_data_get_asn = make_request(url=peering_url_get_asn)
        if peering_data_get_asn:
            data = peering_data_get_asn.get("data")
            if data:
                if data[0]["policy_general"] == "Open":
                    name = data[0]["name"]
                    request_peers = {}
                    request_peers["asn"] = peer.get("asn")
                    request_peers["passive"] = True
                    request_peers["neighbor_ipv4"] = peer.get("ipaddr4")
                    request_peers["neighbor_ipv6"] = peer.get("ipaddr6")
                    if peer.get("asn") in duplicate_asns:
                        if peer.get("ipaddr6") is None:
                            index_from_ip = get_last_segment_v4(peer.get("ipaddr4"))
                        else:
                            index_from_ip = get_last_segment_v6(peer.get("ipaddr6"))
                        request_peers["name"] = name + " " + index_from_ip
                        request_peers["slug"] = (
                            slugify(name).replace("-", "_") + "_" + index_from_ip
                        )
                    else:
                        request_peers["name"] = name
                        request_peers["slug"] = slugify(name).replace("-", "_")
                    request_peers["type"] = "peering"

                    new_bird_peers_upstreams.append(request_peers)

new_bird_peers_upstreams.sort(key=lambda x: x["asn"])
yaml_data = yaml.dump(new_bird_peers_upstreams, default_flow_style=False)
print(yaml_data)
