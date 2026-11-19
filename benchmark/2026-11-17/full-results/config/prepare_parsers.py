import pathlib,urllib.request,tarfile,io,concurrent.futures,subprocess
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');root=base/'tools/RepoAudit/lib/vendor'
items={'c':'cd44a2b1364d26d80daa208d3caf659a4c4e953d','cpp':'12bd6f7e96080d2e70ec51d4068f2f66120dde35','java':'e10607b45ff745f5f876bfa3e94fbcc6b44bdc11','python':'710796b8b877a970297106e5bbc8e2afa47f86ec','go':'12fe553fdaaa7449f764bc876fd777704d4fb752'}
def get(item):
 lang,sha=item;p=root/('tree-sitter-'+lang)
 if (p/'grammar.js').exists():return lang+' exists'
 data=urllib.request.urlopen('https://codeload.github.com/tree-sitter/tree-sitter-'+lang+'/tar.gz/'+sha,timeout=240).read();temp=root/('extract-'+lang);temp.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:t.extractall(temp,filter='data')
 if p.exists():p.rename(root/('incomplete-'+lang))
 next(temp.iterdir()).rename(p);temp.rmdir();return lang+' ready'
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(get,items.items()):print(result,flush=True)
subprocess.run(['python','build.py'],cwd=base/'tools/RepoAudit/lib',check=True)
(base/'config/parsers-ready').write_text('ready')
