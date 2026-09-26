FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
        apt-utils ca-certificates curl wget git sudo zip unzip gnupg software-properties-common \
        openssh-server build-essential python3 python3-pip python3-requests pipx \
        nano vim htop tmux screen tree jq bash-completion man-db locales cron rsyslog dbus \
        iputils-ping net-tools iproute2 dnsutils traceroute whois netcat-openbsd socat tcpdump \
        strace bc wireguard-tools dumb-init \
    && rm -rf /var/lib/apt/lists/*
RUN locale-gen en_US.UTF-8 && update-locale

RUN curl -fsSL https://code-server.dev/install.sh | sh

ARG NVM_VERSION=v0.39.5
RUN mkdir -p /opt/nvm-seed \
    && curl -4 -fsSL --retry 3 "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" -o /tmp/nvm-install.sh \
    && NVM_DIR=/opt/nvm-seed PROFILE=/dev/null bash /tmp/nvm-install.sh \
    && bash -c 'export NVM_DIR=/opt/nvm-seed && . "$NVM_DIR/nvm.sh" && nvm install --lts && nvm alias default "lts/*" && nvm cache clear' \
    && rm -f /tmp/nvm-install.sh

RUN sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/; s/^#?PasswordAuthentication\s+.*/PasswordAuthentication no/; s/^#?PrintMotd\s+.*/PrintMotd yes/' /etc/ssh/sshd_config \
    && mkdir -p /run/sshd /etc/wireguard \
    && printf '* soft nofile 1048576\n* hard nofile 1048576\n' > /etc/security/limits.conf

COPY scripts/bench-setup.sh /opt/benchpress/scripts/
RUN bash /opt/benchpress/scripts/bench-setup.sh develop

COPY scripts/ /opt/benchpress/scripts/
COPY motd/ /etc/update-motd.d/
RUN chmod 755 /opt/benchpress/scripts/*.sh /etc/update-motd.d/00-benchpress-welcome \
    && find /etc/update-motd.d -type f ! -name 00-benchpress-welcome -exec chmod -x {} +

RUN rm -f /etc/ssh/ssh_host_*
CMD ["/opt/benchpress/scripts/boot.sh"]
