import asyncio, logging, time
logging.basicConfig(level=logging.INFO, filename='C:\\test_server.log', force=True)
log = logging.getLogger('test')
async def h(r,w): pass
async def main():
    s = await asyncio.start_server(h, '0.0.0.0', 14433)
    log.info('SERVER_STARTED')
    async with s:
        await s.serve_forever()
asyncio.run(main())
