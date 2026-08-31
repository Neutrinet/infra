{{ ansible_managed | comment }}

/var/log/nextcloud/{{ nextcloud_owner }}/nextcloud.log {
    daily
    rotate 30
    missingok
    notifempty
    compress
    delaycompress
}
