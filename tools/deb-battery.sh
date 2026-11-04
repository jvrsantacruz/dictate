#!/bin/sh
# deb-battery.sh — prove a .deb installs, removes, upgrades and fails cleanly.
#
# Given one .deb, runs the full maintainer-script battery: fresh install,
# reinstall, remove, install-after-remove, purge, upgrade from the same tree
# repacked at 0~old, downgrade, and the failure paths (broken postinst, prerm,
# preinst), each repaired the way an admin would. Ends with a summary and
# exits non-zero on any failure. Needs root; use --docker for clean containers.
#
# Usage:
#   deb-battery.sh [--docker IMAGE]... [--break SCRIPT]... [--smoke CMD]
#                  [--no-lintian] PKG.deb
#
#   --docker IMAGE  run the battery inside a clean IMAGE container, once per
#                   IMAGE given; the .deb is mounted read-only
#   --break SCRIPT  break an extra maintainer script (postrm) and check dpkg
#                   survives; postinst, prerm and preinst are always broken
#   --smoke CMD     run CMD after every successful install (quoted command)
#   --no-lintian    skip lintian (run by default, fatal on any finding)
# Deliberate shellcheck exceptions, file wide: A && ok || bad is safe because ok and
# bad always succeed; word splitting on package paths never carries spaces; and
# /etc/os-release cannot be followed statically.
# shellcheck disable=SC2013,SC2015,SC2086,SC2116,SC2120,SC1091
set -u
export DEBIAN_FRONTEND=noninteractive

MARK='battery-forced-failure'
PASSED=0; FAILED=0; SKIPPED=0
DOCKERS=''; BREAKS=''; SMOKE=''; LINTIAN=1; DEBS=''

ok()   { printf 'ok   %s\n' "$1"; PASSED=$((PASSED+1)); }
bad()  { printf 'FAIL %s\n' "$1"; FAILED=$((FAILED+1)); }
skip() { printf 'skip %s\n' "$1"; SKIPPED=$((SKIPPED+1)); }

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
die() { printf 'deb-battery: %s\n' "$1" >&2; exit 2; }

# ---------- dpkg helpers ----------

pstatus() { dpkg-query -W -f='${db:Status-Abbrev}' "$PKG" 2>/dev/null | tr -d ' '; }
pver()    { dpkg-query -W -f='${Version}' "$PKG" 2>/dev/null; }
installed() { [ "$(pstatus)" = 'ii' ]; }
in_state()  { [ "$(pstatus)" = "$1" ]; }
absent()    { ! dpkg-query -W "$PKG" >/dev/null 2>&1; }

ensure_absent() {
  absent && return 0
  dpkg --purge --force-all "$PKG" >/dev/null 2>&1 || true
  absent || die "cannot clean state of $PKG before the next step"
}

# Install a deb: dpkg first, apt-get -f to complete missing dependencies.
# $1 is an exit check, the rest are dpkg flags; the file is always $DEB.
install_pkg() {
  dpkg -i "$@" "$DEB" >/dev/null 2>&1 || apt-get -y -f install >/dev/null 2>&1
  installed
}

# Regular files dpkg still lists after --remove: only conffiles may remain.
# The deb's own conffiles list, not dpkg's: dpkg drops /var/lib/dpkg/info on remove.
leftover_files() {
  conf="$WORK/ctl/conffiles"
  dpkg -L "$PKG" 2>/dev/null | while IFS= read -r f; do
    [ -f "$f" ] || continue
    { [ -s "$conf" ] && awk '{print $NF}' "$conf" | grep -qxF "$f"; } && continue
    printf '%s\n' "$f"
  done
}

# Nothing of the file list may survive a purge, except shared directories.
purge_leftovers() {
  for f in $FILES; do
    [ -d "$f" ] && continue
    [ ! -e "$f" ] && [ ! -L "$f" ] || printf '%s\n' "$f"
  done
}

break_installed() { sed -i "2a echo '$MARK' >&2; exit 1 # $MARK" "/var/lib/dpkg/info/$PKG.$1"; }
fix_installed()   { sed -i "/$MARK/d" "/var/lib/dpkg/info/$PKG.$1"; }

# Repack $DEB at another version, optionally sabotaging one maintainer script.
repack() { # repack VERSION [script-to-break] outfile
  rm -rf "$WORK/r"; mkdir -p "$WORK/r"
  dpkg-deb -R "$DEB" "$WORK/r"
  sed -i "s/^Version: .*/Version: $1/" "$WORK/r/DEBIAN/control"
  [ -n "${2:-}" ] && sed -i "2a echo '$MARK' >&2; exit 1 # $MARK" "$WORK/r/DEBIAN/$2"
  dpkg-deb --root-owner-group --build "$WORK/r" "$3" >/dev/null
}

# ---------- the battery ----------

static_checks() {
  f=$(dpkg-deb -f "$DEB" Package);    [ -n "$f" ] && ok 'field Package' || bad 'field Package'
  f=$(dpkg-deb -f "$DEB" Version);    [ -n "$f" ] && ok 'field Version' || bad 'field Version'
  f=$(dpkg-deb -f "$DEB" Architecture); [ -n "$f" ] && ok 'field Architecture' || bad 'field Architecture'
  f=$(dpkg-deb -f "$DEB" Description);   [ -n "$f" ] && ok 'field Description' || bad 'field Description'

  # Rules 1 and 2: canonical /usr paths, /etc only for conffiles.
  dpkg-deb -c "$DEB" | awk '!/^drwx/{print $NF}' | sed 's|^\./|/|' > "$WORK/files"
  grep -q '^/lib\|^/bin\|^/sbin' "$WORK/files" \
    && bad 'non-canonical /usr paths (usr-merge)' || ok 'canonical /usr paths'
  if dpkg-deb -c "$DEB" | grep -q '\./etc/'; then
    dpkg-deb -e "$DEB" "$WORK/ctl"
    missing=0
    for f in $(grep '^/etc/' "$WORK/files"); do
      [ -s "$WORK/ctl/conffiles" ] && awk '{print $NF}' "$WORK/ctl/conffiles" \
        | grep -qxF "$f" || { echo "  not a conffile: $f"; missing=1; }
    done
    [ "$missing" = 0 ] && ok '/etc files are conffiles' || bad '/etc files are conffiles'
  fi

  # Rule 13: the copyright file must ship.
  grep -q "/usr/share/doc/$PKG/copyright" "$WORK/files" \
    && ok 'copyright file' || bad 'copyright file'

  # Rule 6: every maintainer script parses.
  for s in preinst postinst prerm postrm; do
    [ -f "$WORK/ctl/$s" ] || continue
    if sh -n "$WORK/ctl/$s" 2>"$WORK/err"; then ok "sh -n $s"
    else bad "sh -n $s"; sed 's/^/  /' "$WORK/err"; fi
    command -v shellcheck >/dev/null && shellcheck -s sh "$WORK/ctl/$s" \
      && ok "shellcheck $s" || skip "shellcheck $s"
  done

  # Lintian, fatal on any finding.
  if [ "$LINTIAN" = 1 ]; then
    command -v lintian >/dev/null || apt-get -y install lintian >/dev/null 2>&1 || true
    if command -v lintian >/dev/null; then
      if lintian --fail-on warning,info --display-info "$DEB" >"$WORK/lint" 2>&1; then
        ok 'lintian'
      else
        bad 'lintian'; sed 's/^/  /' "$WORK/lint"
      fi
    else
      skip 'lintian (not available)'
    fi
  fi
}

flow_lifecycle() {
  ensure_absent
  install_pkg && ok 'fresh install' || bad 'fresh install'
  [ "$(pver)" = "$VER" ] && ok 'installed version' || bad 'installed version'
  dpkg --audit | grep -q "$PKG" && bad 'dpkg --audit clean' || ok 'dpkg --audit clean'
  smoke_check 'smoke after install'

  install_pkg && ok 'reinstall' || bad 'reinstall'

  dpkg --remove "$PKG" >/dev/null 2>&1
  if in_state 'rc'; then
    ok 'remove leaves deinstall+config'
    f=$(leftover_files); [ -z "$f" ] && ok 'remove keeps only conffiles' || { bad 'remove keeps only conffiles'; echo "$f" | sed 's/^/  /'; }
  elif absent; then
    ok 'remove leaves nothing (no conffiles)'
  else
    bad 'remove leaves a sane state'
  fi

  install_pkg && ok 'install after remove' || bad 'install after remove'

  FILES=$(dpkg -L "$PKG")
  dpkg --purge "$PKG" >/dev/null 2>&1
  absent && ok 'purge removes the package' || bad 'purge removes the package'
  f=$(purge_leftovers); [ -z "$f" ] && ok 'purge leaves nothing behind' || { bad 'purge leaves nothing behind'; echo "$f" | sed 's/^/  /'; }
}

flow_upgrade() {
  ensure_absent
  dpkg -i "$OLD_DEB" >/dev/null 2>&1 || apt-get -y -f install >/dev/null 2>&1
  installed && [ "$(pver)" = "$OLD" ] && ok "install $OLD" || bad "install $OLD"
  install_pkg && ok 'upgrade to current version' || bad 'upgrade to current version'
  [ "$(pver)" = "$VER" ] && ok 'upgraded version' || bad 'upgraded version'
}

flow_downgrade() {
  dpkg -i --force-downgrade "$OLD_DEB" >/dev/null 2>&1
  installed && [ "$(pver)" = "$OLD" ] && ok "downgrade to $OLD" || bad "downgrade to $OLD"
  install_pkg && ok 'restore current version' || bad 'restore current version'
  [ "$(pver)" = "$VER" ] && ok 'restored version' || bad 'restored version'
}

flow_failures() {
  # postinst: install a deb with a broken postinst, dpkg records the
  # half-configured state, audit flags it, the admin repairs and configures.
  if [ -f "$WORK/ctl/postinst" ]; then
    ensure_absent
    repack "$VER" postinst "$WORK/bad-postinst.deb"
    if dpkg -i "$WORK/bad-postinst.deb" >/dev/null 2>&1; then bad 'broken postinst fails install'
    else ok 'broken postinst fails install'; fi
    in_state 'iU' || in_state 'iF' && ok 'half-configured state recorded' || bad 'half-configured state recorded'
    dpkg --audit | grep -q "$PKG" && ok 'dpkg --audit flags it' || bad 'dpkg --audit flags it'
    fix_installed postinst
    dpkg --configure "$PKG" >/dev/null 2>&1
    installed && ok 'postinst repair' || bad 'postinst repair'
  else
    skip 'broken postinst (no postinst)'
  fi

  # prerm: remove fails, the admin fixes the script, remove proceeds.
  p="/var/lib/dpkg/info/$PKG.prerm"
  if [ -f "$p" ]; then
    installed || { ensure_absent; install_pkg; }
    break_installed prerm
    if dpkg --remove "$PKG" >/dev/null 2>&1; then bad 'broken prerm fails remove'
    else ok 'broken prerm fails remove'; fi
    fix_installed prerm
    dpkg --remove "$PKG" >/dev/null 2>&1
    in_state 'rc' && ok 'prerm repair' || bad 'prerm repair'
  else
    skip 'broken prerm (no prerm)'
  fi

  # postrm, on request.
  case " $BREAKS " in
    *" postrm "*)
      p="/var/lib/dpkg/info/$PKG.postrm"
      if [ -f "$p" ]; then
        installed || { ensure_absent; install_pkg; }
        break_installed postrm
        if dpkg --remove "$PKG" >/dev/null 2>&1; then bad 'broken postrm fails remove'
        else ok 'broken postrm fails remove'; fi
        fix_installed postrm
        ensure_absent && ok 'postrm repair' || bad 'postrm repair'
      else
        skip 'broken postrm (no postrm)'
      fi
      ;;
  esac

  # preinst: the upgrade fails, the old version stays installed and configured,
  # then the good version upgrades over it.
  if [ -f "$WORK/ctl/preinst" ]; then
    ensure_absent
    dpkg -i "$OLD_DEB" >/dev/null 2>&1 || apt-get -y -f install >/dev/null 2>&1
    installed || { bad 'setup for broken preinst'; return; }
    if dpkg -i "$BAD_DEB" >/dev/null 2>&1; then bad 'broken preinst fails upgrade'
    else ok 'broken preinst fails upgrade'; fi
    installed && [ "$(pver)" = "$OLD" ] && ok 'old version survives (abort-upgrade)' || bad 'old version survives (abort-upgrade)'
    install_pkg && ok 'upgrade after preinst repair' || bad 'upgrade after preinst repair'
  else
    skip 'broken preinst (no preinst)'
  fi
}

smoke() { [ -n "$SMOKE" ] && sh -c "$SMOKE" >/dev/null 2>&1; }
smoke_check() { if [ -n "$SMOKE" ]; then smoke && ok "$1" || bad "$1"; else skip "$1 (no --smoke)"; fi; }

battery() {
  [ "$(id -u)" = 0 ] || die 'needs root; use --docker IMAGE for a clean container'
  WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
  dpkg-deb -e "$DEB" "$WORK/ctl"
  PKG=$(dpkg-deb -f "$DEB" Package)
  VER=$(dpkg-deb -f "$DEB" Version)
  OLD='0~old'
  repack "$OLD" '' "$WORK/old.deb"; OLD_DEB="$WORK/old.deb"
  [ -f "$WORK/ctl/preinst" ] && repack "$VER" preinst "$WORK/bad.deb"; BAD_DEB="$WORK/bad.deb"
  apt-get update -qq >/dev/null 2>&1 || true

  printf '== %s %s on %s\n' "$PKG" "$VER" "$(. /etc/os-release; echo "$PRETTY_NAME")"
  static_checks
  flow_lifecycle
  flow_upgrade
  flow_downgrade
  flow_failures

  printf '== %d ok, %d failed, %d skipped\n' "$PASSED" "$FAILED" "$SKIPPED"
  [ "$FAILED" = 0 ]
}

run_docker() {
  img=$1; debdir=$(cd "$(dirname "$DEB")" && pwd)
  docker run --rm \
    -v "$(readlink -f "$0"):/battery.sh:ro" -v "$debdir:/debs:ro" \
    -e SMOKE="$SMOKE" -e BREAKS="$(echo $BREAKS)" -e LINTIAN="$LINTIAN" \
    "$img" sh -ec '
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -qq >/dev/null 2>&1 || true
      set --
      if [ -n "$BREAKS" ]; then for b in $BREAKS; do set -- "$@" --break "$b"; done; fi
      [ -n "$SMOKE" ] && set -- "$@" --smoke "$SMOKE"
      [ "$LINTIAN" = 0 ] && set -- "$@" --no-lintian
      exec sh /battery.sh "$@" /debs/'"$(basename "$DEB")"
}

# ---------- args ----------

while [ $# -gt 0 ]; do
  case $1 in
    --docker)      DOCKERS="$DOCKERS $2"; shift 2;;
    --break)      BREAKS="$BREAKS $2"; shift 2;;
    --smoke)      SMOKE=$2; shift 2;;
    --no-lintian) LINTIAN=0; shift;;
    -h|--help)    usage;;
    --*)          die "unknown option $1";;
    *) DEBS="$DEBS $1"; shift;;
  esac
done
[ -n "$DEBS" ] || usage
for d in $DEBS; do [ -f "$d" ] || die "no such file: $d"; done
[ "$(id -u)" = 0 ] || [ -n "$DOCKERS" ] || die 'needs root; use --docker IMAGE'

rc=0
for deb in $DEBS; do
  DEB=$deb
  if [ -n "$DOCKERS" ]; then
    for img in $DOCKERS; do
      run_docker "$img" || rc=1
    done
  else
    battery || rc=1
  fi
done
exit $rc
