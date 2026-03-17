ARG FRAPPE_BRANCH=version-15

FROM ubuntu:24.04

ARG FRAPPE_BRANCH=version-15
ARG APPS_JSON_BASE64

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install system dependencies for Frappe
RUN apt-get update && apt-get install -y \
    git curl wget sudo nano htop \
    python3 python3-dev python3-pip python3-venv \
    mariadb-server mariadb-client libmariadb-dev \
    redis-server \
    openssh-server \
    wireguard iproute2 \
    node-less \
    xvfb libfontconfig \
    dumb-init jq \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g yarn

# Install wkhtmltopdf
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb \
    && apt-get install -y ./wkhtmltox_0.12.6.1-3.jammy_amd64.deb \
    && rm wkhtmltox_0.12.6.1-3.jammy_amd64.deb

# Configure MariaDB - set root password with native password auth
RUN service mariadb start \
    && mariadb -e "SET PASSWORD FOR 'root'@'localhost' = PASSWORD('frappe');" \
    && mariadb -e "FLUSH PRIVILEGES;" \
    && service mariadb stop \
    && sed -i 's/^bind-address\s*=.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf

# Configure SSH
RUN mkdir -p /var/run/sshd /etc/wireguard/clients \
    && sed -ri 's/^#?PermitRootLogin\s+.*/PermitRootLogin no/' /etc/ssh/sshd_config

# Create frappe user
RUN adduser --disabled-password --gecos "" frappe \
    && usermod -aG sudo frappe \
    && echo "frappe ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/frappe

# Install bench CLI
RUN pip3 install frappe-bench

# Switch to frappe user for bench operations
USER frappe
WORKDIR /home/frappe

# Decode apps.json if provided
RUN if [ -n "${APPS_JSON_BASE64}" ]; then \
    mkdir -p /tmp/frappe && echo "${APPS_JSON_BASE64}" | base64 -d > /tmp/frappe/apps.json; \
    fi

# Initialize bench with apps
RUN export APP_INSTALL_ARGS="" && \
    if [ -f /tmp/frappe/apps.json ]; then \
    export APP_INSTALL_ARGS="--apps_path=/tmp/frappe/apps.json"; \
    fi && \
    bench init ${APP_INSTALL_ARGS} \
    --frappe-branch=${FRAPPE_BRANCH} \
    --no-procfile \
    --no-backups \
    --verbose \
    frappe-bench

WORKDIR /home/frappe/frappe-bench

# Copy scripts
USER root
RUN mkdir -p /var/labsdata/scripts
COPY scripts/ /var/labsdata/scripts/
RUN chmod +x /var/labsdata/scripts/*

EXPOSE 8000 9000 22

CMD ["/var/labsdata/scripts/entry.sh"]
