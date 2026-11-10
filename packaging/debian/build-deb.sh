#!/bin/bash
# Builds the Debian package of the Linux client together with the server it starts: one package, three applications
# (Claudia Composes, Computes and Creates), each with its own launcher, desktop entry, icon and AppStream metadata.
#
#   packaging/debian/build-deb.sh [OUTPUT_DIR]        (default: dist/)
#
# Layout of the package:
#   /opt/claudia/python    the Python 3.14 that runs the server (uv-managed, so it does not depend on the distro)
#   /opt/claudia/venv      the server and its locked dependencies
#   /opt/claudia/web       the built web frontend
#   /opt/claudia/shell     the GTK shell, a pure Python package that runs on the distro's own Python and PyGObject
#   /usr/bin/claudia-composes, claudia-computes, claudia-creates, and for each the .desktop file, the AppStream metadata
#   and the icon
#
# A virtual environment cannot be moved after it was made, so it is made at its final place, /opt/claudia, which is
# why this script writes there and needs to be allowed to (CI: an empty /opt/claudia that the runner user owns). Needs uv, node 22+, npm and dpkg-deb.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="${1:-$root/dist}"
prefix=/opt/claudia
version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$root/clients/linux/src/claudia_shell_gtk/_version.py")"
[ -n "$version" ] || { echo "error: no version in _version.py" >&2; exit 1; }
# Not a release (CI sets DEB_VERSION_SUFFIX=~git20261106.abc1234): sorts before the release it leads to.
version="${version}${DEB_VERSION_SUFFIX:-}"
arch="$(dpkg --print-architecture)"
stage="$(mktemp -d)"
chmod 755 "$stage"
trap 'rm -rf "$stage"' EXIT
apps="$(cd "$root/clients/linux/src" && python3 -c 'from claudia_shell_gtk import identity; print(*identity.names())')"
[ -n "$apps" ] || { echo "error: no apps in identity.py" >&2; exit 1; }
package=claudia-office

if [ -n "$(ls -A "$prefix" 2>/dev/null)" ]; then
    if [ -z "${CLAUDIA_DEB_CLEAN:-}" ]; then
        echo "error: $prefix is not empty. The package is built at that place; empty it, or set CLAUDIA_DEB_CLEAN=1 to let this script do it." >&2
        exit 1
    fi
    find "$prefix" -mindepth 1 -delete
fi

echo "==> web frontend"
(cd "$root/web" && npm ci && npm run build)

echo "==> server environment in $prefix"
mkdir -p "$prefix"
export UV_PYTHON_INSTALL_DIR="$prefix/python" UV_PROJECT_ENVIRONMENT="$prefix/venv" UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
(cd "$root" && uv python install 3.14 && uv sync --locked --no-dev --no-editable --package claudia-server --python 3.14)
cp -r "$root/web/.output/public" "$prefix/web"
mkdir -p "$prefix/shell"
cp -r "$root/clients/linux/src/claudia_shell_gtk" "$prefix/shell/"
find "$prefix/shell" -name __pycache__ -prune -exec rm -rf {} +

echo "==> package tree"
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/share/applications" "$stage/usr/share/metainfo" \
    "$stage/usr/share/icons" "$stage/usr/share/doc/$package"
mkdir -p "$stage/opt"
cp -a "$prefix" "$stage/opt/"
for name in $apps; do
    id="de.claudiaoffice.$name"
    cat > "$stage/usr/bin/claudia-$name" <<LAUNCH
#!/bin/sh
# Starts Claudia ${name}: the GTK shell on the system Python, its server on the Python 3.14 that comes with the package.
export CLAUDIA_SERVER_PYTHON="\${CLAUDIA_SERVER_PYTHON:-$prefix/venv/bin/python}"
export CLAUDIA_WEB_DIR="\${CLAUDIA_WEB_DIR:-$prefix/web}"
export PYTHONPATH="$prefix/shell\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m claudia_shell_gtk $name "\$@"
LAUNCH
    chmod 755 "$stage/usr/bin/claudia-$name"
    source="$root/clients/linux/apps/$name"
    install -m 644 "$source/$id.desktop" "$stage/usr/share/applications/$id.desktop"
    install -m 644 "$source/$id.metainfo.xml" "$stage/usr/share/metainfo/$id.metainfo.xml"
    cp -r "$source/icons/hicolor" "$stage/usr/share/icons/"
done
cp "$root/CHANGELOG.md" "$stage/usr/share/doc/$package/changelog"
gzip -9n "$stage/usr/share/doc/$package/changelog"
cat > "$stage/usr/share/doc/$package/copyright" <<'COPYRIGHT'
Claudia is free software, licensed under the GNU General Public License, version 3 or (at your option) any later
version. On a Debian system the text is in /usr/share/common-licenses/GPL-3. The bundled Python, Node-built web
frontend and Python libraries keep their own licenses (see the files in /opt/claudia).
COPYRIGHT

size="$(du -sk --exclude=DEBIAN "$stage" | cut -f1)"
cat > "$stage/DEBIAN/control" <<CONTROL
Package: $package
Version: $version
Section: editors
Priority: optional
Architecture: $arch
Installed-Size: $size
Depends: python3 (>= 3.12), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-webkit-6.0, libc6 (>= 2.35)
Replaces: claudia-composes
Breaks: claudia-composes
Provides: claudia-composes
Maintainer: Claudia <noreply@claudiaoffice.de>
Homepage: https://github.com/claudiaoffice/claudia
Description: Claudia office suite with an assistant on your own computer
 Three applications, each with its own start button: Claudia Composes (text),
 Claudia Computes (spreadsheets) and Claudia Creates (presentations).
 Documents are shared live, with an AI that runs where you decide.
 This package holds the desktop windows and the server they start, with the
 Python it needs, so nothing else has to be installed.
CONTROL
# The bundled Python is not the distro's: dpkg must not look for byte-compiled files to clean, and nothing to configure.
mkdir -p "$out"
deb="$out/${package}_${version}_${arch}.deb"
dpkg-deb --root-owner-group -Zxz --build "$stage" "$deb"
echo "==> $deb"
dpkg-deb --info "$deb" | sed -n 1,12p
