import base64
import binascii
import io
import warnings
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import PrivateDocument, PrivateAsset, User, now
from ..security import authenticated
from ..document_schema import validate_document

router = APIRouter(tags=['Private notebooks'])


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)


class Save(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: StrictInt = Field(ge=0, le=9007199254740990)
    document: dict


class Upload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data: str = Field(min_length=1, max_length=6_000_000)


def owned(db, user, document_id):
    doc = db.scalar(select(PrivateDocument).where(PrivateDocument.id == document_id, PrivateDocument.owner_id == user.id))
    if not doc:
        raise HTTPException(404, 'Notebook not found')
    return doc


@router.get('/documents')
def listing(user: User = Depends(authenticated), db: Session = Depends(get_db)):
    return [{'id': d.id, 'title': d.title, 'revision': d.revision, 'updated_at': d.updated_at} for d in db.scalars(select(PrivateDocument).where(PrivateDocument.owner_id == user.id).order_by(PrivateDocument.updated_at.desc()))]


@router.post('/documents', status_code=201)
def create(body: Create, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    stamp = now().isoformat(); doc_id, page_id = str(uuid4()), str(uuid4())
    document = dict(schemaVersion=1, id=doc_id, kind='lesson', visibility='private', title=body.title, createdAt=stamp, updatedAt=stamp, creationDate=stamp[:10], revision=0, activePageId=page_id, pages=[dict(id=page_id, width=900, height=1273, objects=[])])
    db.add(PrivateDocument(id=doc_id, owner_id=user.id, title=body.title, revision=0, body=document)); db.commit()
    return document


@router.get('/documents/{document_id}')
def read(document_id: str, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    return owned(db, user, document_id).body


@router.put('/documents/{document_id}')
def save(document_id: str, body: Save, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    current = owned(db, user, document_id)
    try:
        document = validate_document(body.document)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise HTTPException(422, 'Invalid finite document')
    if document['id'] != document_id or document['createdAt'] != current.body['createdAt']:
        raise HTTPException(422, 'Notebook identity cannot change')
    assets = {o['assetId'] for p in document['pages'] for o in p['objects'] if o['type'] == 'image'}
    found = set(db.scalars(select(PrivateAsset.id).where(PrivateAsset.document_id == document_id, PrivateAsset.id.in_(assets)))) if assets else set()
    if found != assets:
        raise HTTPException(422, 'An image is unavailable in this notebook')
    document = {**document, 'revision': body.expected_revision + 1, 'updatedAt': now().isoformat()}
    result = db.execute(update(PrivateDocument).where(PrivateDocument.id == document_id, PrivateDocument.owner_id == user.id, PrivateDocument.revision == body.expected_revision).values(body=document, title=document['title'], revision=document['revision'], updated_at=now()))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, 'A newer version exists. Download your draft before reopening the saved notebook.')
    db.commit()
    return document


@router.post('/documents/{document_id}/assets', status_code=201)
def upload(document_id: str, body: Upload, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    owned(db, user, document_id)
    try:
        raw = base64.b64decode(body.data, validate=True)
        if len(raw) > 4 * 1024 * 1024: raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=['PNG', 'JPEG']) as source:
                if source.width * source.height > 8_000_000 or getattr(source, 'n_frames', 1) != 1: raise ValueError()
                source.load(); normalized = ImageOps.exif_transpose(source).convert('RGBA')
            output = io.BytesIO(); normalized.save(output, format='PNG'); png = output.getvalue()
            if len(png) > 32 * 1024 * 1024: raise ValueError()
    except (ValueError, binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Choose a single-frame PNG or JPEG up to 4 MB and 8 million pixels')
    asset = PrivateAsset(document_id=document_id, png=png, width=normalized.width, height=normalized.height)
    db.add(asset); db.commit()
    return {'assetId': asset.id, 'width': asset.width, 'height': asset.height}


@router.get('/documents/{document_id}/assets/{asset_id}')
def image(document_id: str, asset_id: str, user: User = Depends(authenticated), db: Session = Depends(get_db)):
    owned(db, user, document_id)
    asset = db.scalar(select(PrivateAsset).where(PrivateAsset.id == asset_id, PrivateAsset.document_id == document_id))
    if not asset: raise HTTPException(404, 'Image not found')
    return Response(asset.png, media_type='image/png', headers={'Content-Disposition': 'inline; filename="image.png"'})
