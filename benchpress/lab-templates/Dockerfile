# syntax=docker/dockerfile:1
ARG FRAPPE_BRANCH=version-15

FROM frappe/build:${FRAPPE_BRANCH}

USER root

ENV DEBIAN_FRONTEND=noninteractive

# --- Layer 1: System deps (rarely changes, always cached) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    mariadb-server mariadb-client \
    redis-server \
    openssh-server \
    sudo nano htop \
    net-tools iproute2 wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# --- Layer 2: Service configs (rarely changes) ---
RUN mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld \
    && mkdir -p /var/run/sshd \
    && sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -ri 's/^#?PasswordAuthentication\s+.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && echo "frappe ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/frappe

# Copy all scripts (entry.sh, install-apps.sh, create-site.sh, setup-site.sh)
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

# Write common_site_config for local MariaDB + Redis
RUN echo '{"db_host":"127.0.0.1","db_port":3306,"redis_cache":"redis://127.0.0.1:6379","redis_queue":"redis://127.0.0.1:6379","redis_socketio":"redis://127.0.0.1:6379"}' \
    > sites/common_site_config.json

# --- Layer 4: Install apps (changes when apps list changes) ---
ARG APPS_JSON=[]
RUN /opt/benchpress/scripts/install-apps.sh "$APPS_JSON"

# --- Layer 5: Create site (needs MariaDB + Redis running in-layer) ---
ARG SITE_NAME=site1.localhost
ARG ADMIN_PASSWORD=admin

USER root
RUN /opt/benchpress/scripts/create-site.sh "$SITE_NAME" "$ADMIN_PASSWORD" "$APPS_JSON"

USER frappe
WORKDIR /home/frappe/frappe-bench

EXPOSE 8000 9000 22

CMD ["/opt/benchpress/scripts/entry.sh"]
