import pathlib,json,time,hashlib,gzip,tarfile,io,subprocess
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17')
shared=pathlib.Path('/vol1/1000/game_data02/mygoldmine-benchmark-images/2026-11-17')
while not (shared/'download-ready').exists(): time.sleep(15)
root=shared/'image-cache'
m=json.loads((root/'source-manifest.json').read_text())
descriptors=[m['config']]+m['layers'];chunk=8*1024*1024;repo='usestrix/strix-sandbox'
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
