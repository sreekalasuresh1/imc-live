from starlette.responses import JSONResponse


class BodyLimit:
    """Bound chunked bodies before JSON parsing; do not trust Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH'):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        limit = 24 * 1024 * 1024 if scope['path'].startswith('/api/documents/') else 1024 * 1024
        if scope['path']=='/api/homework/drafts/import':limit=64*1024*1024
        elif scope['path'].startswith('/api/homework-portal/assignments/'):limit=20*1024*1024
        elif scope['path'].startswith('/api/student-work/'):limit=20*1024*1024
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            size += len(message.get('body', b''))
            if size > limit:
                return await JSONResponse({'detail': 'Request is too large'}, status_code=413)(scope, receive, send)
            chunks.append(message.get('body', b''))
            if not message.get('more_body', False): break
        pending = True

        async def bounded_receive():
            nonlocal pending
            if pending:
                pending = False
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, bounded_receive, send)
