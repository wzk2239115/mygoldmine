import asyncio
from agents.sandbox.manifest import Manifest,Environment
from strix.runtime.backends import get_backend
async def main():
 client,session=await get_backend('docker')(image='ghcr.io/usestrix/strix-sandbox:1.4.1',manifest=Manifest(entries={},environment=Environment(value={})),exposed_ports=())
 try:print('Strix sandbox backend started successfully',flush=True)
 finally:await client.delete(session)
 print('Strix sandbox backend cleaned up',flush=True)
asyncio.run(main())
