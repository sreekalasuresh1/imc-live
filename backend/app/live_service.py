import copy
import hashlib
import io
import json
import secrets
import time
from uuid import uuid4
from fastapi import HTTPException
from PIL import Image, ImageDraw
from sqlalchemy import select, update, delete
from sqlalchemy.orm import defer
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .models import AuthSession, User, Classroom, ClassAccess, JoinInvitation, PrivateDocument, PrivateAsset, now
from .live_models import LiveBoard, LiveOperation, LiveAsset, LiveTransient
from .security import COOKIE, digest, valid_csrf
from .routes.join import session_state, utc
from .document_schema import validate_document, validate_object, ident, number

def fail(message,status=400): raise HTTPException(status,message)
def access(connection,db,class_id,csrf=None):
    room=db.get(ClassAccess,class_id);classroom=db.get(Classroom,class_id)
    if not room or not room.open or utc(room.expires_at)<=now(): fail('Classroom access has ended.',401)
    auth=db.scalar(select(AuthSession).where(AuthSession.token_hash==digest(connection.cookies.get(COOKIE,'')),AuthSession.expires_at>now()))
    user=db.get(User,auth.user_id) if auth else None
    if user and user.active and user.role=='TEACHER' and classroom and classroom.teacher_id==user.id:
        uid=user.id;teacher=True;token=auth.csrf_token
    else:
        session,state=session_state(connection,db)
        if state['classroom_id']!=class_id: fail('Classroom not found.',404)
        uid=db.get(JoinInvitation,session.invitation_id).student_id;teacher=False;token=session.csrf_token
    if csrf is not None and not valid_csrf(csrf,token): fail('Invalid security token.',403)
    actor=hashlib.sha256((class_id+':'+str(room.generation)+':'+uid).encode()).hexdigest()
    return {'uid':uid,'teacher':teacher,'actor':actor,'generation':room.generation}

def board_for(db,class_id,generation,lock=False,metadata_only=False):
    if lock:
        db.execute(update(ClassAccess).where(ClassAccess.classroom_id==class_id,ClassAccess.open.is_(True),ClassAccess.generation==generation,ClassAccess.expires_at>now()).values(generation=ClassAccess.generation).execution_options(synchronize_session=False))
        db.expire_all()
        room=db.get(ClassAccess,class_id)
        if not room or not room.open or room.generation!=generation or utc(room.expires_at)<=now():fail('Classroom access has ended.',401)
    query=select(LiveBoard).where(LiveBoard.classroom_id==class_id,LiveBoard.generation==generation)
    # Idle peers need permissions and identity, not every stored pen sample.
    # SQLAlchemy still loads the document on demand for a transient or edit.
    if metadata_only:query=query.options(defer(LiveBoard.document),defer(LiveBoard.authors))
    board=db.scalar(query)
    if not board:fail('The teacher has not opened the live board yet.',404)
    return board

def snapshot(board,actor):
    return {'type':'snapshot','board_id':board.id,'sequence':board.sequence,'document':board.document,'actor':actor['actor'],'teacher':actor['teacher'],'can_write':actor['teacher'] or actor['uid'] in board.writers}

def publish(db,class_id,actor,source_id=None):
    if not actor['teacher']:fail('Teacher access required.',403)
    db.execute(update(ClassAccess).where(ClassAccess.classroom_id==class_id).values(generation=ClassAccess.generation));db.expire_all()
    room=db.get(ClassAccess,class_id)
    if not room.open or room.generation!=actor['generation'] or utc(room.expires_at)<=now():fail('Classroom access has ended.',401)
    existing=db.scalar(select(LiveBoard).where(LiveBoard.classroom_id==class_id,LiveBoard.generation==actor['generation']))
    if existing:return snapshot(existing,actor)
    if source_id:
        source=db.scalar(select(PrivateDocument).where(PrivateDocument.id==source_id,PrivateDocument.owner_id==actor['uid']))
        if not source:fail('Private notebook not found.',404)
        doc=copy.deepcopy(source.body)
    else:
        stamp=now().isoformat();pid=str(uuid4());doc=dict(schemaVersion=1,id=str(uuid4()),kind='lesson',visibility='private',title='Live classroom',createdAt=stamp,updatedAt=stamp,creationDate=stamp[:10],revision=0,activePageId=pid,pages=[dict(id=pid,width=900,height=1273,objects=[])])
    for k in ['student','batch','topic','subject']:doc.pop(k,None)
    doc['id']=str(uuid4());doc['revision']=0
    board=LiveBoard(classroom_id=class_id,generation=actor['generation'],sequence=0,document=copy.deepcopy(doc),authors={},writers=[]);db.add(board);db.flush()
    authors={}
    for page in doc['pages']:
        for obj in page['objects']:
            authors[obj['id']]=actor['actor']
            if obj['type']=='image':
                asset=db.scalar(select(PrivateAsset).where(PrivateAsset.id==obj['assetId'],PrivateAsset.document_id==source_id))
                if not asset:fail('Notebook image missing.')
                # Redact RGB as well as alpha: transparent pixels cannot retain private source colors.
                image=Image.open(io.BytesIO(asset.png)).convert('RGBA');draw=ImageDraw.Draw(image)
                for mask in obj.get('masks',[]):draw.polygon([(x*image.width,y*image.height) for x,y in mask['points']],fill=(0,0,0,0))
                image.paste((0,0,0,0),mask=image.getchannel('A').point(lambda a:255 if a==0 else 0))
                output=io.BytesIO();image.save(output,format='PNG');aid=str(uuid4());db.add(LiveAsset(board_id=board.id,id=aid,png=output.getvalue()));obj['assetId']=aid;obj.pop('masks',None)
    validate_document(doc);board.document=copy.deepcopy(doc);board.authors=authors;db.commit();return snapshot(board,actor)

def operation(db,class_id,actor,packet,connection=None):
    if set(packet)!={'type','board_id','operation_id','command'} or packet['type']!='operation' or not ident(packet['operation_id']) or not isinstance(packet['command'],dict):fail('Invalid live operation.')
    board=board_for(db,class_id,actor['generation'],True)
    if connection is not None:actor=access(connection,db,class_id)
    if board.id!=packet['board_id']:fail('This work belongs to an earlier class. Download its recovery copy.',409)
    prior=db.get(LiveOperation,(board.id,packet['operation_id']))
    if prior:
        if prior.actor!=actor['actor'] or prior.request!=packet['command']:fail('Operation identity conflict.',409)
        return {'type':'ack','operation_id':packet['operation_id'],'sequence':prior.sequence}
    cmd=packet['command'];kind=cmd.get('type');doc=copy.deepcopy(board.document);authors=dict(board.authors);writers=list(board.writers)
    page=next((p for p in doc['pages'] if p['id']==cmd.get('page_id')),None)
    if kind=='permission':
        if not actor['teacher'] or set(cmd)!={'type','student_id','allow'} or type(cmd['allow']) is not bool:fail('Teacher access required.',403)
        from .routes.join import member
        if not member(db,class_id,cmd['student_id']):fail('Choose an enrolled student.')
        writers=[s for s in writers if s!=cmd['student_id']]
        if cmd['allow']:writers.append(cmd['student_id'])
        event={'type':'permission'}
    else:
        if not actor['teacher'] and actor['uid'] not in writers:fail('Writing permission is disabled.',403)
        if kind=='add':
            if set(cmd)!={'type','page_id','object'} or not page:fail('Invalid page.')
            obj=cmd['object'];validate_object(obj)
            if obj['type'] in ('image','grid'):fail('Publish protected images/grids from a prepared notebook.')
            if any(obj['id']==o['id'] for p in doc['pages'] for o in p['objects']):fail('Object already exists.',409)
            page['objects'].append(copy.deepcopy(obj));authors[obj['id']]=actor['actor'];event=cmd
        elif kind in ('replace','remove'):
            allowed={'type','page_id','object_id','expected'}|({'object'} if kind=='replace' else set())
            if set(cmd)!=allowed or not page:fail('Invalid object edit.')
            current=next((o for o in page['objects'] if o['id']==cmd['object_id']),None)
            if not current or current!=cmd['expected']:fail('This object changed. Your edit is retained for recovery.',409)
            if current['type'] in ('image','grid') or (not actor['teacher'] and authors.get(current['id'])!=actor['actor']):fail('This object is protected.',403)
            if kind=='replace':
                validate_object(cmd['object'])
                if cmd['object']['id']!=current['id'] or cmd['object']['type'] in ('image','grid'):fail('Invalid replacement.')
                page['objects']=[copy.deepcopy(cmd['object']) if o['id']==current['id'] else o for o in page['objects']]
            else:page['objects']=[o for o in page['objects'] if o['id']!=current['id']]
            event=cmd
        elif kind=='page':
            if not actor['teacher'] or set(cmd)!={'type','page_id'} or not page:fail('Only the teacher can change the shared page.',403)
            doc['activePageId']=page['id'];event=cmd
        elif kind=='newPage':
            if not actor['teacher'] or set(cmd)!={'type','page_id'} or not ident(cmd['page_id']) or any(p['id']==cmd['page_id'] for p in doc['pages']):fail('Invalid new page.',403)
            doc['pages'].append(dict(id=cmd['page_id'],width=900,height=1273,objects=[]));doc['activePageId']=cmd['page_id'];event=cmd
        else:fail('Unsupported live command.')
    board.sequence+=1;doc['revision']=board.sequence;doc['updatedAt']=now().isoformat();validate_document(doc)
    board.document=doc;board.authors=authors;board.writers=writers
    db.add(LiveOperation(board_id=board.id,operation_id=packet['operation_id'],sequence=board.sequence,actor=actor['actor'],request=copy.deepcopy(cmd),event=copy.deepcopy(event)))
    db.execute(delete(LiveTransient).where(LiveTransient.board_id==board.id,LiveTransient.actor==actor['actor']))
    db.commit();return {'type':'ack','operation_id':packet['operation_id'],'sequence':board.sequence}

def transient(db,board,actor,packet):
    if packet.get('type')=='preview' and not actor['teacher'] and actor['uid'] not in board.writers:fail('Writing permission is disabled.',403)
    if set(packet)-{'type','page_id','x','y','color','size','shape','object'}:fail('Invalid preview.')
    if packet.get('page_id') not in [p['id'] for p in board.document['pages']]:fail('Invalid preview page.')
    if packet['type']=='pointer':
        if not number(packet.get('x'),0,900) or not number(packet.get('y'),0,1273) or not number(packet.get('size'),3,40) or packet.get('shape') not in ['dot','ring','cross']:fail('Invalid pointer.')
        import re
        if not isinstance(packet.get('color'),str) or not re.fullmatch('#[a-fA-F0-9]{6}',packet['color']):fail('Invalid pointer color.')
    elif packet['type']=='preview':
        validate_object(packet.get('object'))
        if packet['object']['type'] not in ['stroke','highlighter'] or len(packet['object']['points'])>2000:fail('Invalid stroke preview.')
    else:fail('Invalid transient event.')
    insert=pg_insert if db.bind.dialect.name=='postgresql' else sqlite_insert
    deadline=time.time()+1.2
    statement=insert(LiveTransient).values(board_id=board.id,actor=actor['actor'],body=packet,expires=deadline)
    db.execute(statement.on_conflict_do_update(index_elements=['board_id','actor'],set_={'body':packet,'expires':deadline}));db.execute(delete(LiveTransient).where(LiveTransient.expires<time.time()));db.commit()
