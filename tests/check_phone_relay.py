import asyncio,secrets,urllib.request,urllib.error
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus,ConnectionClosed
BASE='ws://127.0.0.1:8787/mobile/'
ORIGIN='http://127.0.0.1:8787'
async def main():
 room=secrets.token_hex(32)
 try:
  async with connect(BASE+room+'/host',origin='https://wrong.example'):
   raise AssertionError('Wrong origin connected')
 except InvalidStatus as error:
  assert error.response.status_code==403
 try:
  async with connect(BASE+room+'/guest',origin=ORIGIN):
   raise AssertionError('Guest connected without host')
 except InvalidStatus as error:
  assert error.response.status_code==410
 async with connect(BASE+room+'/host',origin=ORIGIN) as host:
  try:
   async with connect(BASE+room+'/host',origin=ORIGIN):raise AssertionError('Duplicate host connected')
  except InvalidStatus as error:assert error.response.status_code==409
  async with connect(BASE+room+'/guest',origin=ORIGIN) as guest:
   assert 'ready' in await host.recv() and 'ready' in await guest.recv()
   wire=secrets.token_bytes(32768)
   await host.send(wire);assert await guest.recv()==wire
   await guest.send('plaintext must not relay')
   try:await guest.recv();raise AssertionError('Invalid frame accepted')
   except ConnectionClosed as error:assert error.rcvd.code==1009
 print('Relay origin, missing host, duplicate role, binary forwarding, and invalid frame checks passed.')
asyncio.run(main())
