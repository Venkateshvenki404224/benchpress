# syntax=docker/dockerfile:1
ARG FRAPPE_BRANCH=version-15

FROM frappe/build:${FRAPPE_BRANCH}

USER root

ENV DEBIAN_FRONTEND=noninteractive

# --- Layer 1: System deps (mariadb-client only, no server) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    mariadb-client \
    redis-server \
    openssh-server \
    sudo nano htop \
    net-tools iproute2 wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# --- Layer 2: Service configs ---
RUN mkdir -p /var/run/sshd \
    && sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -ri 's/^#?PasswordAuthentication\s+.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && echo "frappe ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/frappe

RUN mkdir -p /opt/benchpress/scripts
COPY scripts/ /opt/benchpress/scripts/
RUN chmod +x /opt/benchpress/scripts/*

# --- Layer 3: bench init (changes only when FRAPPE_BRANCH changes) ---
USER frappe
ARG FRAPPE_BRANCH
RUN bench init --frappe-branch ${FRAPPE_BRANCH} \
    --no-backups \
    --skip-redis-config-generation \
    --verbose \
    /home/frappe/frappe-bench

WORKDIR /home/frappe/frappe-bench

# --- Layer 4: Install apps (changes when apps list changes) ---
ARG APPS_JSON=[]
RUN /opt/benchpress/scripts/install-apps.sh "$APPS_JSON"

EXPOSE 8000 9000 22

CMD ["/opt/benchpress/scripts/entry.sh"]
