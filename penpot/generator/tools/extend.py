"""Adds what a freshly built .penpot has and the owner's own (Penpot-saved) file lacks: new pages, their components,
text styles and design tokens. Nothing that is already in the owner's file is changed: its pages, components, tokens
and colours stay as the owner left them (that is the difference to transplant.py, which replaces pages).

    python3 tools/extend.py new.penpot owner.penpot out.penpot "Page one" "Page two" ...

The shapes of the new pages and the ids of the components come from the build, and are the same ids in the owner's
file for what both have (they are made from the names, in the order they are made in)."""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load(path):
    return json.loads(read(path))


def dump(path, data):
    write(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def file_dir(root):
    return [d for d in glob.glob(os.path.join(root, "files", "*")) if os.path.isdir(d)][0]


def page_files(folder):
    return {load(p)["name"]: (p, load(p)) for p in glob.glob(os.path.join(folder, "pages", "*.json"))}


def by_name(folder):
    return {load(p)["name"]: p for p in glob.glob(os.path.join(folder, "*.json"))}


def leaves(node, path=()):
    if "$value" in node:
        yield path, node
    else:
        for k, v in node.items():
            if not k.startswith("$"):
                yield from leaves(v, (*path, k))


new_zip, owner_zip, out_zip, *pages = sys.argv[1:]
tmp = tempfile.mkdtemp()
new, owner = os.path.join(tmp, "new"), os.path.join(tmp, "owner")
for z, d in ((new_zip, new), (owner_zip, owner)):
    subprocess.run(["unzip", "-q", z, "-d", d], check=True)

nf, of = file_dir(new), file_dir(owner)
new_id, owner_id = os.path.basename(nf), os.path.basename(of)
npages, opages = page_files(nf), page_files(of)


def rewrite(text):
    return text.replace(new_id, owner_id)


# 1. pages: the shapes of each new page, and the page record at the end of the owner's order
index = max(p["index"] for _, p in opages.values()) + 1
for name in pages:
    if name in opages:
        sys.exit(f'"{name}" is already in the owner file; extend.py only adds pages')
    path, rec = npages[name]
    rec = dict(rec, index=index)
    index += 1
    dump(os.path.join(of, "pages", os.path.basename(path)), rec)
    shutil.copytree(path[:-5], os.path.join(of, "pages", rec["id"]))
    for f in glob.glob(os.path.join(of, "pages", rec["id"], "*.json")):
        write(f, rewrite(read(f)))

# 2. components whose main shapes are on the new pages (and any the owner file does not have)
have = {os.path.basename(p) for p in glob.glob(os.path.join(of, "components", "*.json"))}
added_components = 0
for p in glob.glob(os.path.join(nf, "components", "*.json")):
    if os.path.basename(p) in have:
        continue
    write(os.path.join(of, "components", os.path.basename(p)), rewrite(read(p)))
    added_components += 1

# 3. text styles and colours by name
added_styles = 0
for kind in ("typographies", "colors"):
    mine = by_name(os.path.join(of, kind))
    for name, p in by_name(os.path.join(nf, kind)).items():
        if name not in mine:
            write(os.path.join(of, kind, os.path.basename(p)), rewrite(read(p)))
            added_styles += 1

# 4. tokens: what the owner's sets lack is added to them; what they have is left as the owner has it
ntok, otok = load(os.path.join(nf, "tokens.json")), load(os.path.join(of, "tokens.json"))
added_tokens = 0
for set_name, node in ntok.items():
    if set_name.startswith("$") or set_name not in otok:
        continue
    for path, leaf in leaves(node):
        target = otok[set_name]
        for k in path[:-1]:
            target = target.setdefault(k, {})
        if path[-1] not in target:
            target[path[-1]] = leaf
            added_tokens += 1
dump(os.path.join(of, "tokens.json"), otok)

if os.path.exists(out_zip):
    os.remove(out_zip)
subprocess.run(
    ["zip", "-q", "-r", "-X", os.path.abspath(out_zip), "manifest.json", "files", "objects"], cwd=owner, check=True
)
added = f"{added_components} components, {added_styles} styles, {added_tokens} tokens"
print(f"{len(pages)} pages, {added} added to {out_zip}")
