
FROM ubuntu:24.04

# ==========================================================
# LAB MANAGER - AAEE ACADEMIC UBUNTU IMAGE
# ==========================================================

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

ENV LAB_INSTITUTION=AAEE
ENV LAB_INSTITUTION_NAME="Academia de Altos Estudos e Estratégicos"

# ==========================================================
# 1. INSTALAÇÃO DE PACOTES                                    
# ==========================================================

RUN apt-get update && apt-get install -y \
    openssh-server \
    sudo \
    nginx \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    git \
    vim \
    nano \
    iproute2 \
    iputils-ping \
    net-tools \
    dnsutils \
    traceroute \
    tcpdump \
    nmap \
    netcat-openbsd \
    procps \
    htop \
    unzip \
    zip \
    ca-certificates \
    tzdata \
    lsb-release \
    util-linux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ==========================================================
# 2. ESTRUTURA DE DIRETÓRIOS
# ==========================================================

RUN mkdir -p \
    /var/run/sshd \
    /var/www/html \
    /var/www/html/assets \
    /workspace \
    /etc/lab-manager \
    /etc/update-motd.d \
    /etc/ssh/sshd_config.d \
    /opt/lab-manager/branding \
    /opt/lab-manager/assets \
    /opt/lab-manager/resources

# ==========================================================
# 3. IDENTIDADE INSTITUCIONAL - AAEE
# ==========================================================

COPY branding/ /opt/lab-manager/branding/
COPY assets/ /opt/lab-manager/assets/
COPY branding/motd /etc/motd

# Verificar ficheiros institucionais essenciais
RUN test -f /opt/lab-manager/branding/index.html \
    && test -f /opt/lab-manager/assets/logo.png \
    && test -f /opt/lab-manager/branding/issue \
    && test -f /opt/lab-manager/branding/motd \
    && test -f /opt/lab-manager/branding/00-header \
    && test -f /opt/lab-manager/branding/10-system \
    && test -f /opt/lab-manager/branding/20-academic

# ==========================================================
# 4. CONFIGURAÇÃO DO MOTD DINÂMICO
# ==========================================================

RUN chmod +x \
    /opt/lab-manager/branding/00-header \
    /opt/lab-manager/branding/10-system \
    /opt/lab-manager/branding/20-academic \
    && chmod 644 \
    /opt/lab-manager/branding/index.html \
    /opt/lab-manager/branding/issue \
    /opt/lab-manager/branding/motd \
    /opt/lab-manager/assets/logo.png

# ==========================================================
# 5. ENTRYPOINT
# ==========================================================

COPY entrypoint.sh /entrypoint.sh

RUN chmod 755 /entrypoint.sh
RUN chmod 755 /etc/motd

# ==========================================================
# 6. CONFIGURAÇÃO SSH
# ==========================================================

RUN printf '%s\n' \
    'UsePAM yes' \
    'PrintMotd no' \
    'PrintLastLog yes' \
    > /etc/ssh/sshd_config.d/00-lab-manager.conf \
    && chmod 644 /etc/ssh/sshd_config.d/00-lab-manager.conf

# ==========================================================
# 7. CONFIGURAÇÃO NGINX
# ==========================================================

RUN mkdir -p \
    /var/log/nginx \
    /var/lib/nginx \
    /var/cache/nginx \
    && chmod 755 /var/www/html

# ==========================================================
# 8. PORTAS
# ==========================================================

# 443: nothing serves HTTPS in this image (LAB_HTTPS_ENABLED publishes it when one does)
EXPOSE 22 80

# ==========================================================
# 9. METADADOS
# ==========================================================

LABEL maintainer="AAEE - Lab Manager"
LABEL institution="AAEE"
LABEL description="Academic Virtual Laboratory - Ubuntu 24.04"
LABEL version="2.2"

# ==========================================================
# 10. INICIALIZAÇÃO
# ==========================================================

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
