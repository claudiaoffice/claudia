#!/bin/sh
# Spike E8.5 (throwaway): builds build/spike-mac-launcher/claudia-composes-spike.pkg on a Mac with Apple Silicon, from
# this checkout. Run it from anywhere:   sh spikes/e8-5-mac-launcher/build-spike-pkg.sh
#
# Needs: uv, Node 22+ and npm (to build), curl, and Apple's own pkgbuild, codesign, iconutil, sips. Downloads the newest
# Node 22 for darwin-arm64 from nodejs.org (checked against its SHASUMS256.txt) to bundle it, as the real package will.
# The server is not bundled: the spike's app starts the checkout's .venv/bin/python (the real package has its own).
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
app=composes
out="$repo/build/spike-mac-launcher"
root="$out/root"
bundle="$root/Applications/claudia $app.app"
runtime="$root/Library/Application Support/Claudia/runtime"

[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo "This spike is built on a Mac with Apple Silicon." >&2; exit 1; }
for tool in uv npm node curl pkgbuild codesign iconutil sips plutil; do
    command -v "$tool" >/dev/null 2>&1 || { echo "missing: $tool" >&2; exit 1; }
done

echo "== the server's Python (.venv), the web app, the client for macOS"
cd "$repo"
uv sync --quiet --no-dev
(cd web && npm ci --silent && npm run build --silent)
(cd clients/neutralino && npm ci --silent && npm run build:macos --silent)
if [ ! -f "clients/neutralino/apps/$app/bin/neutralino-mac_arm64" ] || [ ! -f "clients/neutralino/apps/$app/js/neutralino.js" ]; then
    (cd "clients/neutralino/apps/$app" && npx --yes @neutralinojs/neu update)
fi

echo "== Node 22 for darwin-arm64"
mkdir -p "$out/download"
sums="$(curl -fsSL https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt)"
tarball="$(printf '%s\n' "$sums" | awk '/node-v22\.[0-9.]*-darwin-arm64\.tar\.gz$/ {print $2}')"
expected="$(printf '%s\n' "$sums" | awk -v f="$tarball" '$2 == f {print $1}')"
[ -f "$out/download/$tarball" ] || curl -fsSL -o "$out/download/$tarball" "https://nodejs.org/dist/latest-v22.x/$tarball"
actual="$(shasum -a 256 "$out/download/$tarball" | awk '{print $1}')"
[ "$actual" = "$expected" ] || { echo "SHA-256 of $tarball does not match SHASUMS256.txt" >&2; exit 1; }

echo "== the payload"
rm -rf "$root" && mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources" "$runtime/node/bin" "$runtime/client/apps" "$runtime/spike"
tar -xzf "$out/download/$tarball" -C "$out/download"
cp "$out/download/${tarball%.tar.gz}/bin/node" "$runtime/node/bin/node"
cp "$out/download/${tarball%.tar.gz}/LICENSE" "$runtime/node/LICENSE"
cp -R web/.output/public "$runtime/web"
cp -R clients/neutralino/dist clients/neutralino/package.json "$runtime/client/"
mkdir -p "$runtime/client/apps/$app"
(cd "clients/neutralino/apps/$app" && tar --exclude ./bin -cf - .) | (cd "$runtime/client/apps/$app" && tar -xf -)
cp "$here/prepare.mjs" "$runtime/spike/"
printf "CLAUDIA_SERVER_PYTHON='%s'\n" "$repo/.venv/bin/python" >"$runtime/spike/settings.sh"

cp "$here/launcher.sh" "$bundle/Contents/MacOS/claudia-$app"
chmod 755 "$bundle/Contents/MacOS/claudia-$app"
cp "clients/neutralino/apps/$app/bin/neutralino-mac_arm64" "$bundle/Contents/MacOS/neutralino"
chmod 755 "$bundle/Contents/MacOS/neutralino"
cat >"$bundle/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key><string>claudia-$app</string>
	<key>CFBundleIdentifier</key><string>de.claudiaoffice.$app</string>
	<key>CFBundleName</key><string>claudia $app</string>
	<key>CFBundleDisplayName</key><string>claudia $app</string>
	<key>CFBundleIconFile</key><string>$app</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleShortVersionString</key><string>0.0.1</string>
	<key>CFBundleVersion</key><string>0.0.1</string>
	<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
	<key>LSMinimumSystemVersion</key><string>14.0</string>
	<key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
plutil -lint "$bundle/Contents/Info.plist" >/dev/null

iconset="$out/$app.iconset"
rm -rf "$iconset" && mkdir -p "$iconset"
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "clients/neutralino/apps/$app/icon@4x.png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" "clients/neutralino/apps/$app/icon@4x.png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$bundle/Contents/Resources/$app.icns"

echo "== ad-hoc signatures (Apple Silicon runs no unsigned code)"
codesign --force --sign - "$bundle/Contents/MacOS/neutralino"
codesign --force --sign - "$bundle" || echo "note: the bundle itself could not be signed ad hoc (its executable is a script); go on"

echo "== the package"
plist="$out/component.plist"
pkgbuild --analyze --root "$root" "$plist" >/dev/null
# Otherwise Installer may "relocate" the app to wherever a bundle with the same id already is (a checkout's .app).
plutil -replace 0.BundleIsRelocatable -bool false "$plist"
pkgbuild --root "$root" --component-plist "$plist" --identifier de.claudiaoffice.spike.launcher --version 0.0.1 \
    --install-location / --ownership recommended "$out/claudia-composes-spike.pkg" >/dev/null
echo "built: $out/claudia-composes-spike.pkg"
