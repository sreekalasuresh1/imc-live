import asyncio
import json
import time
from fastapi import APIRouter, Request, Response, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import SessionLocal, get_db
from ..config import settings
from ..live_models import LiveAsset, LiveOperation, LiveTransient
from .. import live_service as service
from ..security import teacher
from ..models import User, PrivateDocument, PrivateAsset, now
from ..live_models import LiveBoard
from .join import owned
import copy
import io
from uuid import uuid4
from PIL import Image

router=APIRouter(tags=['Live classroom'])

@router.get('/classes/{class_id}/live/history')
def history(class_id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id)
    return [dict(id=b.id,generation=b.generation,sequence=b.sequence,created_at=b.created_at) for b in db.scalars(select(LiveBoard).where(LiveBoard.classroom_id==class_id).order_by(LiveBoard.generation.desc()))]

@router.post('/classes/{class_id}/live/{board_id}/retain',status_code=201)
def retain(class_id:str,board_id:str,user:User=Depends(teacher),db:Session=Depends(get_db)):
    owned(db,user,class_id)
    board=db.scalar(select(LiveBoard).where(LiveBoard.id==board_id,LiveBoard.classroom_id==class_id))
    if not board:raise HTTPException(404,'Live session not found')
    doc=copy.deepcopy(board.document);doc['id']=str(uuid4());doc['revision']=0;doc['title']=('Live session '+str(board.generation)+' — '+doc['title'])[:200];doc['createdAt']=doc['updatedAt']=now().isoformat()
    db.add(PrivateDocument(id=doc['id'],owner_id=user.id,title=doc['title'],revision=0,body=copy.deepcopy(doc)));db.flush()
    assets={}
    for page in doc['pages']:
        for obj in page['objects']:
            if obj['type']!='image':continue
            old=obj['assetId']
            if old not in assets:
                asset=db.get(LiveAsset,(board.id,old));im=Image.open(io.BytesIO(asset.png));new=str(uuid4());assets[old]=new
                db.add(PrivateAsset(id=new,document_id=doc['id'],png=asset.png,width=im.width,height=im.height))
            obj['assetId']=assets[old]
    db.get(PrivateDocument,doc['id']).body=copy.deepcopy(doc);db.commit();return {'id':doc['id']}
class Publish(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:str|None=Field(default=None,max_length=80)

@router.post('/classes/{class_id}/live')
def publish(class_id:str,body:Publish,request:Request,db:Session=Depends(get_db)):
    actor=service.access(request,db,class_id,request.headers.get('X-CSRF-Token',''))
    return service.publish(db,class_id,actor,body.source_id)

@router.get('/join/live/{class_id}/state')
def state(class_id:str,request:Request,db:Session=Depends(get_db)):
    actor=service.access(request,db,class_id)
    return service.snapshot(service.board_for(db,class_id,actor['generation']),actor)

@router.get('/join/live/{class_id}/assets/{board_id}/{asset_id}')
def image(class_id:str,board_id:str,asset_id:str,request:Request,db:Session=Depends(get_db)):
    actor=service.access(request,db,class_id);board=service.board_for(db,class_id,actor['generation'])
    if board.id!=board_id:raise HTTPException(404,'Live image not found')
    asset=db.get(LiveAsset,(board_id,asset_id))
    if not asset:raise HTTPException(404,'Live image not found')
    return Response(asset.png,media_type='image/png')

@router.websocket('/join/live/{class_id}/socket')
async def socket(ws:WebSocket,class_id:str):
    if ws.headers.get('origin') not in settings.origins:
        await ws.close(code=1008);return
    await ws.accept()
    try:
        raw=await asyncio.wait_for(ws.receive_text(),timeout=10)
        if len(raw)>4096:await ws.close(code=1009);return
        hello=json.loads(raw)
        if not isinstance(hello,dict) or hello.get('type')!='hello':await ws.close(code=1008);return
        csrf=hello.get('csrf','')
        with SessionLocal() as db:
            actor=service.access(ws,db,class_id,csrf);board=service.board_for(db,class_id,actor['generation']);initial=service.snapshot(board,actor)
        await ws.send_json(initial);board_id=initial['board_id'];sequence=initial['sequence'];permission=initial['can_write'];last_transient='';bucket=time.monotonic();count=0;heartbeat=time.monotonic()
        while True:
            raw=None
            try:raw=await asyncio.wait_for(ws.receive_text(),timeout=.1)
            except asyncio.TimeoutError:pass
            with SessionLocal() as db:
                actor=service.access(ws,db,class_id,csrf);board=service.board_for(db,class_id,actor['generation'],metadata_only=True)
                if board.id!=board_id:await ws.close(code=1008);return
                if raw is not None:
                    if len(raw)>2*1024*1024:await ws.close(code=1009);return
                    if time.monotonic()-bucket>=1:bucket=time.monotonic();count=0
                    count+=1
                    if count>40:await ws.close(code=1008);return
                    packet=json.loads(raw)
                    try:
                        if not isinstance(packet,dict):service.fail('Invalid event.')
                        if packet.get('type')=='operation':reply=service.operation(db,class_id,actor,packet,ws);await ws.send_json(reply)
                        elif packet.get('type') in ['pointer','preview']:service.transient(db,board,actor,packet)
                        else:service.fail('Unsupported event.')
                    except (HTTPException,ValueError,TypeError,KeyError) as e:
                        db.rollback();await ws.send_json({'type':'rejected','operation_id':packet.get('operation_id') if isinstance(packet,dict) else None,'message':e.detail if isinstance(e,HTTPException) else 'Invalid live event.'})
                db.expire_all();board=service.board_for(db,class_id,actor['generation'],metadata_only=True)
                writable=actor['teacher'] or actor['uid'] in board.writers
                if writable!=permission:await ws.send_json({'type':'permission','can_write':writable});permission=writable
                events=db.scalars(select(LiveOperation).where(LiveOperation.board_id==board_id,LiveOperation.sequence>sequence).order_by(LiveOperation.sequence).limit(100)).all()
                for event in events:
                    await ws.send_json({'type':'operation','operation_id':event.operation_id,'sequence':event.sequence,'command':event.event});sequence=event.sequence
                ephemeral=[{'actor':t.actor,'body':t.body,'expires':t.expires} for t in db.scalars(select(LiveTransient).where(LiveTransient.board_id==board_id,LiveTransient.expires>time.time())) if t.actor!=actor['actor']]
                encoded=json.dumps(ephemeral,sort_keys=True)
                if encoded!=last_transient:await ws.send_json({'type':'transients','items':ephemeral});last_transient=encoded
                if time.monotonic()-heartbeat>4:await ws.send_json({'type':'heartbeat'});heartbeat=time.monotonic()
    except (HTTPException,ValueError,KeyError,TypeError,asyncio.TimeoutError):
        await ws.close(code=1008)
    except WebSocketDisconnect:pass
