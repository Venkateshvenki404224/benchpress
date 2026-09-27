#!/bin/bash

service rsyslog start
service dbus start

ssh-keygen -A
service ssh start

[ -f /etc/wireguard/wg0.conf ] && wg-quick up wg0
ln -sf /usr/bin/python3 /usr/bin/python

[ -f /.benchpress_config ] && /opt/benchpress/scripts/restart.sh

exec dumb-init sleep infinity
