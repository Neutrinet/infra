#!/bin/bash

protocol="udp"
tcp_arg=""
port=1194
while getopts "tp:" opt; do
  case $opt in
    t) protocol="tcp"
       tcp_arg="-t"
      ;;
    p) port=$OPTARG
      ;;
    *) echo "Usage: $0 [-t -p <port>] <target ip>"
       exit 1
      ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 [-t -p <port>] <target ip>"
  exit 1
fi

address="$1"

ip_version=4
if [[ $address == *':'* ]]; then
  ip_version=6
fi

value=1
if response=$(check_openvpn $tcp_arg -p "$port" "$address"); then
  value=0
fi

jq -n -c \
  --argjson value "$value" \
  --arg address "$address" \
  --arg port "$port" \
  --arg protocol "$protocol" \
  --arg ip_version "$ip_version" \
  --arg response "$response" \
  '{
    metric: {
      name: "check_openvpn",
      kind: "absolute",
      gauge: { value: $value },
      tags: {
        address: $address,
        port: $port,
        protocol: $protocol,
        ip_version: $ip_version,
        response: $response
      }
    }
  }'
