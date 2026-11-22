"""Adds what a freshly built .penpot has and the owner's own (Penpot-saved) file lacks: new pages, their components,
text styles and design tokens. Nothing that is already in the owner's file is changed: its pages, components, tokens
and colours stay as the owner left them (that is the difference to transplant.py, which replaces pages).

    python3 tools/extend.py new.penpot owner.penpot out.penpot "Page one" "Page two" ...

The shapes of the new pages and the ids of the components come from the build, and are the same ids in the owner's
file for what both have (they are made from the names, in the order they are made in)."""
import glob, json, os, shutil, subprocess, sys, tempfile

new_zip, owner_zip, out_zip, *pages = sys.argv[1:]
tmp = tempfile.mkdtemp()
new, owner = os.path.join(tmp, 'new'), os.path.join(tmp, 'owner')
for z, d in ((new_zip, new), (owner_zip, owner)):
    subprocess.run(['unzip', '-q', z, '-d', d], check=True)

fdir = lambda root: [d for d in glob.glob(os.path.join(root, 'files', '*')) if os.path.isdir(d)][0]
nf, of = fdir(new), fdir(owner)
new_id, owner_id = os.path.basename(nf), os.path.basename(of)
load = lambda p: json.load(open(p))
def dump(p, data):
    json.dump(data, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))

def page_files(f):
    return {load(p)['name']: (p, load(p)) for p in glob.glob(os.path.join(f, 'pages', '*.json'))}

npages, opages = page_files(nf), page_files(of)
rewrite = lambda text: text.replace(new_id, owner_id)

# 1. pages: the shapes of each new page, and the page record at the end of the owner's order
index = max(p['index'] for _, p in opages.values()) + 1
for name in pages:
    if name in opages:
        sys.exit(f'"{name}" is already in the owner file; extend.py only adds pages')
    path, rec = npages[name]
    rec = dict(rec, index=index)
    index += 1
    dump(os.path.join(of, 'pages', os.path.basename(path)), rec)
    shutil.copytree(path[:-5], os.path.join(of, 'pages', rec['id']))
    for f in glob.glob(os.path.join(of, 'pages', rec['id'], '*.json')):
        text = rewrite(open(f).read())  # read before open(f, 'w') truncates the file
        open(f, 'w').write(text)

# 2. components whose main shapes are on the new pages (and any the owner file does not have)
page_ids = {npages[n][1]['id'] for n in pages}
have = {os.path.basename(p) for p in glob.glob(os.path.join(of, 'components', '*.json'))}
added_components = 0
for p in glob.glob(os.path.join(nf, 'components', '*.json')):
    if os.path.basename(p) in have:
        continue
    open(os.path.join(of, 'components', os.path.basename(p)), 'w').write(rewrite(open(p).read()))
    added_components += 1

# 3. text styles and colours by name
def by_name(folder):
    return {load(p)['name']: p for p in glob.glob(os.path.join(folder, '*.json'))}
added_styles = 0
for kind in ('typographies', 'colors'):
    mine = by_name(os.path.join(of, kind))
    for name, p in by_name(os.path.join(nf, kind)).items():
        if name not in mine:
            open(os.path.join(of, kind, os.path.basename(p)), 'w').write(rewrite(open(p).read()))
            added_styles += 1

# 4. tokens: what the owner's sets lack is added to them; what they have is left as the owner has it
def leaves(node, path=()):
    if '$value' in node:
        yield path, node
    else:
        for k, v in node.items():
            if not k.startswith('$'):
                yield from leaves(v, path + (k,))
ntok, otok = load(os.path.join(nf, 'tokens.json')), load(os.path.join(of, 'tokens.json'))
added_tokens = 0
for set_name, node in ntok.items():
    if set_name.startswith('$') or set_name not in otok:
        continue
    for path, leaf in leaves(node):
        target = otok[set_name]
        for k in path[:-1]:
            target = target.setdefault(k, {})
        if path[-1] not in target:
            target[path[-1]] = leaf
            added_tokens += 1
dump(os.path.join(of, 'tokens.json'), otok)

if os.path.exists(out_zip):
    os.remove(out_zip)
subprocess.run(f'cd "{owner}" && zip -q -r -X "{os.path.abspath(out_zip)}" manifest.json files objects', shell=True, check=True)
print(f'{len(pages)} pages, {added_components} components, {added_styles} styles, {added_tokens} tokens added to {out_zip}')
