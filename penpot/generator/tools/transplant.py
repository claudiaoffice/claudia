"""Puts the pages of a freshly built .penpot into the owner's own (Penpot-saved) file. The library, tokens, colours and
text styles stay the owner's; the ids of the components and their main shapes are the same in both (they are made from
the names), so the owner's component records stay valid. Pages given on the command line are replaced; the rest stay."""
import glob, json, os, shutil, subprocess, sys, tempfile

new_zip, user_zip, out_zip, *names = sys.argv[1:]
tmp = tempfile.mkdtemp()
new, user = os.path.join(tmp, 'new'), os.path.join(tmp, 'user')
for z, d in ((new_zip, new), (user_zip, user)):
    subprocess.run(['unzip', '-q', z, '-d', d], check=True)

def file_dir(root):
    return [d for d in glob.glob(os.path.join(root, 'files', '*')) if os.path.isdir(d)][0]

def page_ids(fdir):
    return {json.load(open(f))['name']: json.load(open(f))['id'] for f in glob.glob(os.path.join(fdir, 'pages', '*.json'))}

nf, uf = file_dir(new), file_dir(user)
np_, up_ = page_ids(nf), page_ids(uf)
names = names or list(np_)
new_file_id, user_file_id = os.path.basename(nf), os.path.basename(uf)

count = 0
for name in names:
    npid, upid = np_[name], up_[name]
    shutil.rmtree(os.path.join(uf, 'pages', upid))
    os.makedirs(os.path.join(uf, 'pages', upid))
    for f in glob.glob(os.path.join(nf, 'pages', npid, '*.json')):
        text = open(f).read()
        for n2 in np_:
            text = text.replace(np_[n2], up_[n2])
        text = text.replace(new_file_id, user_file_id)
        open(os.path.join(uf, 'pages', upid, os.path.basename(f)), 'w').write(text)
        count += 1
# the thumbnails Penpot kept are pictures of the old pages; it makes new ones
for t in ('frame', 'component'):
    shutil.rmtree(os.path.join(uf, 'thumbnails', t), ignore_errors=True)
shutil.rmtree(os.path.join(user, 'objects'), ignore_errors=True)
if os.path.exists(out_zip):
    os.remove(out_zip)
subprocess.run('zip -q -X -r %s manifest.json files' % os.path.abspath(out_zip), shell=True, check=True, cwd=user)
print('%d shape files of %s put into %s' % (count, ', '.join(names), out_zip))
