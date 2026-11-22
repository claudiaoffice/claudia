"""Puts the pages of a freshly built .penpot into the owner's own (Penpot-saved) file. The library, tokens, colours and
text styles stay the owner's; the ids of the components and their main shapes are the same in both (they are made from
the names), so the owner's component records stay valid. Pages given on the command line are replaced; the rest stay."""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

new_zip, user_zip, out_zip, *names = sys.argv[1:]
tmp = tempfile.mkdtemp()
new, user = os.path.join(tmp, "new"), os.path.join(tmp, "user")
for z, d in ((new_zip, new), (user_zip, user)):
    subprocess.run(["unzip", "-q", z, "-d", d], check=True)


def file_dir(root):
    return [d for d in glob.glob(os.path.join(root, "files", "*")) if os.path.isdir(d)][0]


def page_ids(fdir):
    ids = {}
    for path in glob.glob(os.path.join(fdir, "pages", "*.json")):
        with open(path) as f:
            page = json.load(f)
        ids[page["name"]] = page["id"]
    return ids


nf, uf = file_dir(new), file_dir(user)
np_, up_ = page_ids(nf), page_ids(uf)
names = names or list(np_)
new_file_id, user_file_id = os.path.basename(nf), os.path.basename(uf)

count = 0
for name in names:
    npid, upid = np_[name], up_[name]
    shutil.rmtree(os.path.join(uf, "pages", upid))
    os.makedirs(os.path.join(uf, "pages", upid))
    for f in glob.glob(os.path.join(nf, "pages", npid, "*.json")):
        with open(f) as source:
            text = source.read()
        for n2 in np_:
            text = text.replace(np_[n2], up_[n2])
        text = text.replace(new_file_id, user_file_id)
        with open(os.path.join(uf, "pages", upid, os.path.basename(f)), "w") as target:
            target.write(text)
        count += 1
# the thumbnails Penpot kept are pictures of the old pages; it makes new ones
for t in ("frame", "component"):
    shutil.rmtree(os.path.join(uf, "thumbnails", t), ignore_errors=True)
shutil.rmtree(os.path.join(user, "objects"), ignore_errors=True)
if os.path.exists(out_zip):
    os.remove(out_zip)
subprocess.run(["zip", "-q", "-X", "-r", os.path.abspath(out_zip), "manifest.json", "files"], check=True, cwd=user)
print(f"{count} shape files of {', '.join(names)} put into {out_zip}")
