import pathlib,urllib.request,json,socket,concurrent.futures,time,hashlib,gzip,shutil,tarfile,io,subprocess
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');root=base/'image-cache';root.mkdir(exist_ok=True)
original=socket.getaddrinfo
socket.getaddrinfo=lambda host,port,family=0,type=0,proto=0,flags=0:original(host,port,socket.AF_INET,type,proto,flags)
repo='usestrix/strix-sandbox';token=json.load(urllib.request.urlopen('https://ghcr.io/token?scope=repository:'+repo+':pull',timeout=30))['token']
def request(kind,ref,extra=None):
 h={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json'};h.update(extra or {})
 return urllib.request.Request('https://ghcr.io/v2/'+repo+'/'+kind+'/'+ref,headers=h)
def manifest(ref):
 data=urllib.request.urlopen(request('manifests',ref),timeout=30).read()
 if ref.startswith('sha256:'):assert hashlib.sha256(data).hexdigest()==ref.split(':')[1]
 return json.loads(data)
m=manifest('1.4.1')
if 'manifests' in m:
 descriptor=next(x for x in m['manifests'] if x.get('platform',{}).get('architecture')=='amd64' and x.get('platform',{}).get('os')=='linux');m=manifest(descriptor['digest'])
(root/'source-manifest.json').write_text(json.dumps(m,indent=2));descriptors=[m['config']]+m['layers'];chunk=8*1024*1024;tasks=[]
for d in descriptors:
 digest=d['digest'].split(':')[1];folder=root/digest;folder.mkdir(exist_ok=True)
 for start in range(0,d['size'],chunk):tasks.append((d,start,min(start+chunk,d['size'])-1,folder/str(start)))
def fetch(item):
 d,start,end,p=item;size=end-start+1
 if p.exists() and p.stat().st_size==size:return
 for attempt in range(5):
  try:
   with urllib.request.urlopen(request('blobs',d['digest'],{'Range':f'bytes={start}-{end}'}),timeout=90) as r:
    data=r.read(size+1);assert len(data)==size,(len(data),size)
   q=p.with_suffix('.tmp');q.write_bytes(data);q.replace(p);return
  except Exception:
   if attempt==4:raise
   time.sleep(2**attempt)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 futures=[pool.submit(fetch,x) for x in tasks]
 for i,f in enumerate(concurrent.futures.as_completed(futures),1):f.result();print('chunks',i,'/',len(tasks),flush=True)
blobs={}
for d in descriptors:
 digest=d['digest'].split(':')[1];p=root/(digest+'.blob');h=hashlib.sha256()
 with p.open('wb') as out:
  for start in range(0,d['size'],chunk):
   data=(root/digest/str(start)).read_bytes();h.update(data);out.write(data)
 assert h.hexdigest()==digest;blobs[d['digest']]=p
config=blobs[m['config']['digest']].read_bytes();c=json.loads(config);layers=[]
for i,d in enumerate(m['layers']):
 p=root/('layer-'+str(i)+'.tar');blob=blobs[d['digest']]
 if 'gzip' not in d.get('mediaType',''):raise RuntimeError('Unsupported layer encoding')
 h=hashlib.sha256()
 with gzip.open(blob,'rb') as src,p.open('wb') as out:
  while data:=src.read(1024*1024):h.update(data);out.write(data)
 assert 'sha256:'+h.hexdigest()==c['rootfs']['diff_ids'][i];layers.append(p)
 print('verified layer',i+1,'/',len(m['layers']),flush=True)
config_name=m['config']['digest'].split(':')[1]+'.json';archive=root/'strix-sandbox.tar'
with tarfile.open(archive,'w') as t:
 for name,data in [(config_name,config),('manifest.json',json.dumps([{'Config':config_name,'RepoTags':['ghcr.io/usestrix/strix-sandbox:1.4.1'],'Layers':[p.name for p in layers]}]).encode())]:
  info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
 for p in layers:t.add(p,arcname=p.name,recursive=False)
subprocess.run(['docker','load','-i',str(archive)],check=True)
actual=subprocess.check_output(['docker','image','inspect','ghcr.io/usestrix/strix-sandbox:1.4.1','--format','{{.Id}}'],text=True).strip();assert actual==m['config']['digest']
(base/'config/strix-image-provenance.json').write_text(json.dumps({'registry':'ghcr.io','repository':repo,'tag':'1.4.1','platform':'linux/amd64','image_id':actual,'compressed_layer_hashes_verified':True,'uncompressed_diff_ids_verified':True},indent=2));print('IMAGE READY',actual,flush=True)
