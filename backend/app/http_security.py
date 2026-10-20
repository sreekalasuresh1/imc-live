"""Fail-closed transport boundary, with headers on early error responses too."""
from urllib.parse import urlsplit
from starlette.datastructures import Headers,MutableHeaders
from starlette.responses import JSONResponse
from .config import settings

class SecurityBoundary:
    def __init__(self,app,config=None):self.app=app;self.config=config or settings
    async def __call__(self,scope,receive,send):
        if scope['type'] not in ['http','websocket']:return await self.app(scope,receive,send)
        config=self.config;headers=Headers(scope=scope);production=config.environment=='production'
        async def secured(message):
            if message['type']=='http.response.start':
                h=MutableHeaders(scope=message)
                for key,value in {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Cross-Origin-Resource-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=(), usb=()'}.items():h[key]=value
                if production:
                    h['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                    if scope.get('scheme') in ['https','wss']:h['Strict-Transport-Security']='max-age=31536000'
            await send(message)
        async def reject(message,status):
            if scope['type']=='websocket':await send({'type':'websocket.close','code':1008})
            else:await JSONResponse({'detail':message},status_code=status)(scope,receive,secured)
        if production:
            try:
                raw=headers.get('host','');authority=urlsplit('//'+raw);host=authority.hostname;_=authority.port
                if len(headers.getlist('host'))!=1 or authority.username or authority.password or authority.path or authority.query or authority.fragment or '\\' in raw or any(c.isspace() for c in raw):host=None
            except ValueError:host=None
            if host not in {urlsplit(o).hostname for o in config.origins}:return await reject('Host is not allowed.',400)
            # Only Uvicorn's explicitly trusted proxy may set the ASGI scheme.
            if scope.get('scheme') not in ['https','wss']:return await reject('HTTPS is required.',403)
        if scope['type']=='websocket' or scope.get('method') not in ['GET','HEAD','OPTIONS']:
            if headers.get('origin') not in config.origins:return await reject('Request origin is not allowed',403)
        await self.app(scope,receive,secured)
