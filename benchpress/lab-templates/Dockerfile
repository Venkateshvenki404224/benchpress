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
    screen \
    curl ca-certificates \
    sudo nano htop \
    net-tools iproute2 wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# --- Layer 2: Service configs ---
RUN mkdir -p /var/run/sshd \
    && sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -ri 's/^#?PasswordAuthentication\s+.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && echo "frappe ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/frappe

# Only install-apps.sh runs during the build (Layer 4). Copying it alone here keeps the runtime
# scripts out of the early layers, so editing serve.sh/entry.sh/setup-site.sh does not invalidate
# bench init, the app clone (the codeload throttle lives here) or bench build — see the tail COPY.
RUN mkdir -p /opt/benchpress/scripts
COPY scripts/install-apps.sh /opt/benchpress/scripts/
RUN chmod +x /opt/benchpress/scripts/install-apps.sh

ARG CODE_SERVER_VERSION=4.96.4
RUN curl -fsSL "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server_${CODE_SERVER_VERSION}_amd64.deb" -o /tmp/cs.deb \
    && apt-get update && apt-get install -y --no-install-recommends /tmp/cs.deb \
    && rm -rf /tmp/cs.deb /var/lib/apt/lists/*

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

# --- Layer 5: Bundle every app's assets, once per image ---
# install-apps.sh passes --skip-assets, so only frappe's bundles come from bench init.
RUN bench build --production

USER root

# --- Layer 6: Runtime scripts, last so a script fix rebuilds only this layer ---
# The whole scripts/ dir (install-apps.sh included again, harmlessly) so entry.sh, serve.sh,
# setup-site.sh, linkuser.sh and restart.sh are present for the container at runtime.
COPY scripts/ /opt/benchpress/scripts/
RUN chmod +x /opt/benchpress/scripts/*

EXPOSE 8000 9000 22 8080

CMD ["/opt/benchpress/scripts/entry.sh"]
