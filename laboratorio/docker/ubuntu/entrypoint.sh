
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# LAB MANAGER - CONTAINER ENTRYPOINT
# AAEE ACADEMIC UBUNTU IMAGE
# ==========================================================

log() {
    echo "[LAB-MANAGER] $*"
}

fail() {
    log "ERRO: $*"
    exit 1
}

# ==========================================================
# 1. CONFIGURAÇÃO E COMPATIBILIDADE
# ==========================================================

# Utilizador: LAB_USER tem prioridade; SSH_USER é compatível.
LAB_USER="${LAB_USER:-${SSH_USER:-student}}"

# Password: mantém compatibilidade com SSH_PASSWORD.
LAB_PASSWORD="${LAB_PASSWORD:-${SSH_PASSWORD:-}}"

# Sudo: aceita LAB_SUDO e LAB_SUDO_DEFAULT.
LAB_SUDO="${LAB_SUDO:-${LAB_SUDO_DEFAULT:-true}}"

LAB_SSH_PASSWORD_AUTH="${LAB_SSH_PASSWORD_AUTH:-no}"
LAB_SSH_ROOT_LOGIN="${LAB_SSH_ROOT_LOGIN:-no}"
LAB_SSH_AUTHORIZED_KEYS="${LAB_SSH_AUTHORIZED_KEYS:-}"

# Instituição
LAB_INSTITUTION="${LAB_INSTITUTION:-AAEE}"
LAB_INSTITUTION_NAME="${LAB_INSTITUTION_NAME:-Academia de Altos Estudos e Estratégicos}"
LAB_NAME="${LAB_NAME:-Laboratório Académico}"

# Identificação académica
LAB_STUDENT_NAME="${LAB_STUDENT_NAME:-Não definido}"
LAB_STUDENT_NUMBER="${LAB_STUDENT_NUMBER:-Não definido}"
LAB_STUDENT_COURSE="${LAB_STUDENT_COURSE:-Não definido}"
LAB_STUDENT_CLASS="${LAB_STUDENT_CLASS:-Não definido}"
LAB_SUBJECT="${LAB_SUBJECT:-Não definido}"
LAB_TEACHER="${LAB_TEACHER:-Não definido}"

# Máquina
LAB_MACHINE_NAME="${LAB_MACHINE_NAME:-$(hostname)}"
LAB_WEB_ENABLED="${LAB_WEB_ENABLED:-true}"

# Diretórios
BRANDING_DIR="/opt/lab-manager/branding"
ASSETS_DIR="/opt/lab-manager/assets"
WEB_ROOT="/var/www/html"

# ==========================================================
# 2. VALIDAÇÕES
# ==========================================================

if [[ ! "$LAB_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
    fail "Nome de utilizador inválido: $LAB_USER"
fi

case "$LAB_SUDO" in
    true|false) ;;
    *) fail "LAB_SUDO deve ser true ou false." ;;
esac

case "$LAB_SSH_PASSWORD_AUTH" in
    yes|no) ;;
    *) fail "LAB_SSH_PASSWORD_AUTH deve ser yes ou no." ;;
esac

case "$LAB_SSH_ROOT_LOGIN" in
    yes|no|prohibit-password) ;;
    *) fail "LAB_SSH_ROOT_LOGIN inválido." ;;
esac

case "$LAB_WEB_ENABLED" in
    true|false) ;;
    *) fail "LAB_WEB_ENABLED deve ser true ou false." ;;
esac

# ==========================================================
# 3. PREPARAR SISTEMA
# ==========================================================

mkdir -p \
    /var/run/sshd \
    "$WEB_ROOT/assets" \
    /etc/lab-manager \
    /etc/ssh/sshd_config.d \
    /etc/update-motd.d

chmod 755 /var/run/sshd

# ==========================================================
# 4. CRIAR OU REUTILIZAR UTILIZADOR
# ==========================================================

if ! id "$LAB_USER" >/dev/null 2>&1; then
    log "A criar utilizador $LAB_USER"

    useradd \
        --create-home \
        --shell /bin/bash \
        "$LAB_USER"
else
    log "Utilizador $LAB_USER já existe."
fi

USER_HOME="$(getent passwd "$LAB_USER" | cut -d: -f6)"

[[ -n "$USER_HOME" && -d "$USER_HOME" ]] \
    || fail "Diretório home inválido para $LAB_USER."

# ==========================================================
# 5. CONFIGURAR PASSWORD
# ==========================================================

if [[ -n "$LAB_PASSWORD" ]]; then
    log "A configurar palavra-passe de $LAB_USER"

    printf '%s:%s\n' "$LAB_USER" "$LAB_PASSWORD" | chpasswd
else
    log "Nenhuma palavra-passe fornecida."
    passwd -l "$LAB_USER" >/dev/null 2>&1 || true
fi

# ==========================================================
# 6. CONFIGURAR SUDO
# ==========================================================

if [[ "$LAB_SUDO" == "true" ]]; then
    # O grupo e a regra sudo existem apenas dentro deste container.
    getent group sudo >/dev/null 2>&1 || groupadd sudo
    usermod -aG sudo "$LAB_USER"

    # Permitir administração do laboratório sem pedir password a cada comando.
    cat > /etc/sudoers.d/lab-manager-students <<'SUDOERS'
%sudo ALL=(ALL:ALL) NOPASSWD:ALL
SUDOERS

    chown root:root /etc/sudoers.d/lab-manager-students
    chmod 0440 /etc/sudoers.d/lab-manager-students
    visudo -cf /etc/sudoers.d/lab-manager-students >/dev/null \
        || fail "Regra sudo inválida."
    log "Permissões sudo activadas para $LAB_USER."
else
    rm -f /etc/sudoers.d/lab-manager-students
    deluser "$LAB_USER" sudo >/dev/null 2>&1 || true
    log "Permissões sudo desactivadas para $LAB_USER."
fi

# ==========================================================
# 7. CONFIGURAR SSH AUTHORIZED KEYS
# ==========================================================

SSH_DIR="$USER_HOME/.ssh"
AUTHORIZED_KEYS="$SSH_DIR/authorized_keys"

if [[ -n "$LAB_SSH_AUTHORIZED_KEYS" ]]; then
    log "A configurar chaves SSH para $LAB_USER"

    install -d \
        -m 700 \
        -o "$LAB_USER" \
        -g "$LAB_USER" \
        "$SSH_DIR"

    printf '%s\n' "$LAB_SSH_AUTHORIZED_KEYS" > "$AUTHORIZED_KEYS"

    chown "$LAB_USER:$LAB_USER" "$AUTHORIZED_KEYS"
    chmod 600 "$AUTHORIZED_KEYS"
else
    log "Nenhuma chave SSH pública fornecida."
fi

# ==========================================================
# 8. CONFIGURAR SSH SERVER
# ==========================================================

SSHD_CONFIG="/etc/ssh/sshd_config"
SSHD_DROPIN="/etc/ssh/sshd_config.d/00-lab-manager.conf"

[[ -f "$SSHD_CONFIG" ]] \
    || fail "Ficheiro sshd_config não encontrado."

# Remover diretivas antigas para evitar valores contraditórios.
sed -i \
    -e '/^[[:space:]]*Include[[:space:]]/d' \
    -e '/^[[:space:]]*PasswordAuthentication[[:space:]]/d' \
    -e '/^[[:space:]]*PubkeyAuthentication[[:space:]]/d' \
    -e '/^[[:space:]]*PermitRootLogin[[:space:]]/d' \
    -e '/^[[:space:]]*KbdInteractiveAuthentication[[:space:]]/d' \
    -e '/^[[:space:]]*Banner[[:space:]]/d' \
    "$SSHD_CONFIG"

# Garantir inclusão das configurações adicionais.
sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' "$SSHD_CONFIG"

cat > "$SSHD_DROPIN" <<EOF
PasswordAuthentication $LAB_SSH_PASSWORD_AUTH
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin $LAB_SSH_ROOT_LOGIN
UsePAM yes
PrintMotd no
Banner /etc/issue

# Manter a ligação SSH activa
ClientAliveInterval 60
ClientAliveCountMax 10
TCPKeepAlive yes
EOF

chmod 644 "$SSHD_DROPIN"

# ==========================================================
# 9. PERMISSÕES DO UTILIZADOR
# ==========================================================

chown "$LAB_USER:$LAB_USER" "$USER_HOME"
chmod 700 "$USER_HOME"

if [[ -d "$SSH_DIR" ]]; then
    chown -R "$LAB_USER:$LAB_USER" "$SSH_DIR"
    chmod 700 "$SSH_DIR"

    if [[ -f "$AUTHORIZED_KEYS" ]]; then
        chmod 600 "$AUTHORIZED_KEYS"
    fi
fi

# ==========================================================
# 10. IDENTIDADE INSTITUCIONAL E TERMINAL
# ==========================================================

if [[ -d "$BRANDING_DIR" ]]; then

    # O issue é texto estático apresentado antes da autenticação SSH.
    if [[ -f "$BRANDING_DIR/issue" ]]; then
        install -o root -g root -m 0644 "$BRANDING_DIR/issue" /etc/issue
    fi

    # Os scripts genéricos de branding podem continuar activos.
    for script in 00-header 10-system 20-academic; do
        if [[ -f "$BRANDING_DIR/$script" ]]; then
            install -o root -g root -m 0755 \
                "$BRANDING_DIR/$script" \
                "/etc/update-motd.d/$script"
        fi
    done

    # O MOTD personalizado é gerado abaixo e lê os dados persistidos
    # em /etc/lab-manager/container.conf em cada autenticação SSH.

    # Evita que o código do script seja mostrado literalmente pelo SSH.
    : > /etc/motd
    chown root:root /etc/motd
    chmod 0644 /etc/motd
fi

# Normalizar PAM: uma única chamada ao MOTD dinâmico.
# Remove entradas antigas/repetidas para evitar imprimir o MOTD duas vezes.
PAM_SSHD="/etc/pam.d/sshd"
[[ -f "$PAM_SSHD" ]] || fail "Ficheiro PAM não encontrado: $PAM_SSHD"

sed -i \
    -e '/^[[:space:]]*session[[:space:]].*pam_motd\.so/d' \
    -e '/^[[:space:]]*# Lab Manager: MOTD dinâmico/d' \
    "$PAM_SSHD"

cat >> "$PAM_SSHD" <<'PAM_MOTD'

# Lab Manager: executar o MOTD dinâmico uma única vez.
session optional pam_motd.so motd=/run/motd.dynamic
PAM_MOTD

# O MOTD estático nunca deve conter o script Bash.
: > /etc/motd
chown root:root /etc/motd
chmod 0644 /etc/motd

# ==========================================================
# 11. DISPONIBILIZAR LOGÓTIPO
# ==========================================================

if [[ -f "$ASSETS_DIR/logo.png" ]]; then
    install -m 644 \
        "$ASSETS_DIR/logo.png" \
        "$WEB_ROOT/assets/logo.png"
else
    log "AVISO: logo.png não encontrado."
fi

# ==========================================================
# 12. GERAR PÁGINA WEB ACADÉMICA
# ==========================================================

if [[ "$LAB_WEB_ENABLED" == "true" ]]; then

    TEMPLATE="$BRANDING_DIR/index.html"

    [[ -f "$TEMPLATE" ]] \
        || fail "Template Web não encontrado: $TEMPLATE"

    log "A gerar página Web académica..."

    export LAB_MACHINE_NAME
    export LAB_INSTITUTION
    export LAB_INSTITUTION_NAME
    export LAB_NAME
    export LAB_STUDENT_NAME
    export LAB_STUDENT_NUMBER
    export LAB_STUDENT_COURSE
    export LAB_STUDENT_CLASS
    export LAB_SUBJECT
    export LAB_TEACHER
    export LAB_USER

    python3 - <<'PY'
import html
import os
from pathlib import Path

template = Path("/opt/lab-manager/branding/index.html")
destination = Path("/var/www/html/index.html")

fields = [
    "LAB_MACHINE_NAME",
    "LAB_INSTITUTION",
    "LAB_INSTITUTION_NAME",
    "LAB_NAME",
    "LAB_STUDENT_NAME",
    "LAB_STUDENT_NUMBER",
    "LAB_STUDENT_COURSE",
    "LAB_STUDENT_CLASS",
    "LAB_SUBJECT",
    "LAB_TEACHER",
    "LAB_USER",
]

content = template.read_text(encoding="utf-8")

for field in fields:
    value = html.escape(os.environ.get(field, "Não definido"))
    content = content.replace("{{" + field + "}}", value)

destination.write_text(content, encoding="utf-8")
destination.chmod(0o644)
PY

    log "Página Web gerada em $WEB_ROOT/index.html"

else
    log "Página Web desativada pela configuração."
fi

# ==========================================================
# 13. GUARDAR CONFIGURAÇÃO DO CONTAINER
# ==========================================================

# Guardar os valores com escaping seguro para serem lidos pelo script MOTD.
export LAB_USER LAB_SUDO LAB_SSH_PASSWORD_AUTH LAB_MACHINE_NAME
export LAB_INSTITUTION LAB_INSTITUTION_NAME LAB_NAME
export LAB_STUDENT_NAME LAB_STUDENT_NUMBER LAB_STUDENT_COURSE
export LAB_STUDENT_CLASS LAB_SUBJECT LAB_TEACHER

python3 - <<'PYCONFIG'
import os
import shlex
from pathlib import Path

keys = [
    "LAB_USER", "LAB_SUDO", "LAB_SSH_PASSWORD_AUTH", "LAB_MACHINE_NAME",
    "LAB_INSTITUTION", "LAB_INSTITUTION_NAME", "LAB_NAME",
    "LAB_STUDENT_NAME", "LAB_STUDENT_NUMBER", "LAB_STUDENT_COURSE",
    "LAB_STUDENT_CLASS", "LAB_SUBJECT", "LAB_TEACHER",
]
path = Path("/etc/lab-manager/container.conf")
path.write_text("".join(f"{key}={shlex.quote(os.environ.get(key, 'Não definido'))}\n" for key in keys), encoding="utf-8")
path.chmod(0o600)
PYCONFIG

# Criar um MOTD verdadeiramente personalizado para cada container.
cat > /etc/update-motd.d/90-lab-manager <<'MOTD'
#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG=/etc/lab-manager/container.conf
[[ -r "$CONFIG" ]] && source "$CONFIG"

: "${LAB_STUDENT_NAME:=Não definido}"
: "${LAB_STUDENT_NUMBER:=Não definido}"
: "${LAB_STUDENT_COURSE:=Não definido}"
: "${LAB_STUDENT_CLASS:=Não definido}"
: "${LAB_SUBJECT:=Não definido}"
: "${LAB_TEACHER:=Não definido}"
: "${LAB_MACHINE_NAME:=$(hostname)}"
: "${LAB_INSTITUTION_NAME:=Academia de Altos Estudos e Estratégicos}"
: "${LAB_NAME:=Laboratório Académico Virtual}"

printf '\n'
printf '  ============================================================\n'
printf '  %s\n' "$LAB_INSTITUTION_NAME"
printf '  %s\n' "$LAB_NAME"
printf '  ============================================================\n'
printf '  BEM-VINDO(A), %s\n' "$LAB_STUDENT_NAME"
printf '\n'
printf '  DADOS ACADÉMICOS\n'
printf '  Nome       : %s\n' "$LAB_STUDENT_NAME"
printf '  Número     : %s\n' "$LAB_STUDENT_NUMBER"
printf '  Curso      : %s\n' "$LAB_STUDENT_COURSE"
printf '  Turma      : %s\n' "$LAB_STUDENT_CLASS"
printf '  Disciplina : %s\n' "$LAB_SUBJECT"
printf '  Docente    : %s\n' "$LAB_TEACHER"
printf '\n'
printf '  AMBIENTE DE TRABALHO\n'
printf '  Máquina    : %s\n' "$LAB_MACHINE_NAME"
printf '  Sistema    : %s\n' "$(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-Ubuntu}")"
printf '\n'
printf '  Utilize este ambiente para realizar as actividades académicas.\n'
printf '  As sessões e actividades poderão ser acompanhadas pelo docente.\n'
printf '  ============================================================\n\n'
MOTD
chown root:root /etc/update-motd.d/90-lab-manager
chmod 0755 /etc/update-motd.d/90-lab-manager

chmod 600 /etc/lab-manager/container.conf

# ==========================================================
# 14. VALIDAR SERVIÇOS
# ==========================================================

log "A validar configuração SSH..."

/usr/sbin/sshd -t \
    || fail "Configuração SSH inválida."

if [[ "$LAB_WEB_ENABLED" == "true" ]]; then
    log "A validar configuração Nginx..."

    nginx -t \
        || fail "Configuração Nginx inválida."
fi

# ==========================================================
# 15. INICIAR SERVIÇOS
# ==========================================================

if [[ "$LAB_WEB_ENABLED" == "true" ]]; then
    log "A iniciar Nginx..."

    service nginx start \
        || fail "Não foi possível iniciar o Nginx."
fi

log "------------------------------------------"
log "Container preparado."
log "Máquina: $LAB_MACHINE_NAME"
log "Utilizador: $LAB_USER"
log "Sudo: $LAB_SUDO"
log "SSH Password Authentication: $LAB_SSH_PASSWORD_AUTH"
log "SSH Public Key Authentication: enabled"
log "SSH Root Login: $LAB_SSH_ROOT_LOGIN"
log "Web Enabled: $LAB_WEB_ENABLED"
log "------------------------------------------"

log "A iniciar SSH..."

exec /usr/sbin/sshd -D -e
