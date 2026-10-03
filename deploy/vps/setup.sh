#!/usr/bin/env bash
# LAIN online World Core on a fresh Ubuntu 24.04 VPS (Hetzner CX22 or similar).
#
#   bash setup.sh [--branch NAME] [--host NAME]
#
# Run as root. Safe to run again (lain-update does): it updates the code and
# keeps the world, the players and the Groq key. The whole script lives in
# main() so bash has read all of it before git rewrites this file.
set -euo pipefail

REPO=https://github.com/webtilians/lain.git

main() {
  local branch=experiment/layer-03-ttl host=""
  [ -f /etc/lain/branch ] && branch=$(cat /etc/lain/branch)
  [ -f /etc/lain/host ] && host=$(cat /etc/lain/host)
  while [ $# -gt 0 ]; do
    case "$1" in
      --branch) branch=$2; shift 2 ;;
      --host) host=$2; shift 2 ;;
      *) echo "Opción desconocida: $1" >&2; exit 2 ;;
    esac
  done
  [ "$(id -u)" -eq 0 ] || { echo "Ejecuta este script como root." >&2; exit 1; }
  if [ -z "$host" ]; then
    # Free HTTPS name: 1.2.3.4 -> 1-2-3-4.sslip.io resolves back to this IP.
    local ip
    ip=$(ip -4 route get 1.1.1.1 | awk '{for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit }}')
    host=${ip//./-}.sslip.io
  fi

  step "Paquetes del sistema"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get -y -q -o Dpkg::Options::=--force-confold upgrade
  apt-get install -y -q git python3-venv sqlite3 ufw caddy unattended-upgrades
  # Security updates every day, without automatic reboots (the world would drop).
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

  step "SSH solo con llave y cortafuegos"
  if [ -s /root/.ssh/authorized_keys ]; then
    cat > /etc/ssh/sshd_config.d/10-lain.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
    sshd -t && (systemctl reload ssh 2>/dev/null || systemctl reload sshd)
  else
    echo "AVISO: root no tiene llave SSH; dejo las contraseñas como estaban."
  fi
  ufw allow OpenSSH >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null

  step "Usuario y carpetas"
  id lain >/dev/null 2>&1 || useradd --system --home-dir /var/lib/lain --shell /usr/sbin/nologin lain
  install -d -o lain -g lain -m 700 /var/lib/lain
  install -d -o root -g root -m 700 /etc/lain /var/backups/lain
  if [ ! -f /etc/lain/lain.env ]; then
    # Characters use scripted dialogue until lain-set-groq-key adds the AI.
    install -m 600 /dev/null /etc/lain/lain.env
    echo "LAIN_LLM_ENABLED=0" > /etc/lain/lain.env
  fi
  echo "$branch" > /etc/lain/branch
  echo "$host" > /etc/lain/host

  step "Código del motor ($branch)"
  if [ ! -d /opt/lain/.git ]; then
    # Only the server half of the repository; the game art stays on GitHub.
    git clone -q --depth 1 --filter=blob:none --sparse --branch "$branch" "$REPO" /opt/lain
    git -C /opt/lain sparse-checkout set server tools packaging deploy
  else
    git -C /opt/lain fetch -q --depth 1 origin "$branch"
    git -C /opt/lain reset -q --hard FETCH_HEAD
  fi
  # The repository tracks a Windows .venv (pyvenv.cfg included) that git
  # deletes on update, so the server's Python lives outside the checkout.
  [ -x /opt/lain-venv/bin/python ] || python3 -m venv /opt/lain-venv
  rm -rf /opt/lain/.venv
  /opt/lain-venv/bin/pip install -q --disable-pip-version-check -r /opt/lain/requirements.txt
  # The service cannot write to /opt/lain, so compile once here.
  /opt/lain-venv/bin/python -m compileall -q /opt/lain/server /opt/lain/tools /opt/lain/packaging >/dev/null
  install -m 755 /opt/lain/deploy/vps/bin/* /usr/local/sbin/

  step "Servicio, copias diarias y HTTPS ($host)"
  [ -f /var/lib/lain/online-world.db ] && lain-backup
  install -m 644 /opt/lain/deploy/vps/systemd/* /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable -q lain.service lain-backup.timer
  systemctl restart lain.service
  systemctl start lain-backup.timer
  sed "s/__HOST__/$host/" /opt/lain/deploy/vps/Caddyfile.template > /etc/caddy/Caddyfile
  local check
  if ! check=$(caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1); then
    echo "$check" >&2; exit 1
  fi
  systemctl enable -q caddy
  systemctl restart caddy

  step "Comprobación"
  local ok=""
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 "https://$host/health" >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
  done
  echo
  if [ -n "$ok" ]; then
    echo "LISTO: el mundo está encendido en https://$host"
  else
    echo "El motor arrancó, pero https://$host aún no responde."
    echo "Revisa: systemctl status lain caddy  (el certificado puede tardar un minuto)"
  fi
  git -C /opt/lain log -1 --format='Versión: %h %s'
}

step() { printf '\n== %s ==\n' "$1"; }

main "$@"
