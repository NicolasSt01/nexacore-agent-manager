import re

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_superadmin
from ..models import Agency, User
from ..schemas import AgencyOut, AgencyUpdate, AgencyUserCreate, AgencyUserOut
from ..security import hash_password
from ..slugs import slugify


router = APIRouter(prefix="/agency", tags=["Agency"])
MAX_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


@router.get("", response_model=AgencyOut)
def get_agency(user: User = Depends(get_current_user)):
    return user.agency


@router.patch("", response_model=AgencyOut)
def update_agency(
    payload: AgencyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agency = user.agency
    values = payload.model_dump(exclude_unset=True)
    if "slug" in values and values["slug"]:
        candidate = slugify(values["slug"])
        if db.scalar(select(Agency).where(Agency.slug == candidate, Agency.id != agency.id)):
            raise HTTPException(status_code=409, detail="That identifier is already in use")
        values["slug"] = candidate
    if "brand_color" in values and not re.fullmatch(r"#[0-9a-fA-F]{6}", values["brand_color"] or ""):
        raise HTTPException(status_code=400, detail="The color must use the #075985 format")
    for key, value in values.items():
        setattr(agency, key, value)
    db.commit()
    db.refresh(agency)
    return agency


@router.get("/users", response_model=list[AgencyUserOut])
def list_agency_users(db: Session = Depends(get_db), user: User = Depends(require_superadmin)):
    return db.scalars(
        select(User).where(User.agency_id == user.agency_id).order_by(User.created_at.asc())
    ).all()


@router.post("/users", response_model=AgencyUserOut, status_code=status.HTTP_201_CREATED)
def create_agency_user(
    payload: AgencyUserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    """Add a seller (or another superadmin) to the current agency.

    This is how Edgar and Enedina are created. /auth/register always spins up a
    brand new agency, so it can never be used to add a colleague to an existing
    one.
    """
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    member = User(
        agency_id=user.agency_id,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.post("/logo", response_model=AgencyOut)
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="Use a PNG, JPG, WebP or SVG logo")
    data = await file.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="The logo exceeds the 2 MB limit")
    user.agency.logo_data = data
    user.agency.logo_mime = file.content_type
    db.commit()
    db.refresh(user.agency)
    return user.agency


@router.get("/logo")
def get_logo(user: User = Depends(get_current_user)):
    agency = user.agency
    if not agency.logo_data or not agency.logo_mime:
        raise HTTPException(status_code=404, detail="The agency does not have a logo yet")
    return Response(content=agency.logo_data, media_type=agency.logo_mime, headers={"Cache-Control": "no-store"})


@router.delete("/logo", status_code=status.HTTP_204_NO_CONTENT)
def delete_logo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.agency.logo_data = None
    user.agency.logo_mime = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
