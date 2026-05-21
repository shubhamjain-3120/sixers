from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Config
from app.schemas.config import ConfigRead, ConfigUpdate
from datetime import datetime

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_or_create_config(db: Session) -> Config:
    cfg = db.query(Config).filter(Config.id == 1).first()
    if not cfg:
        cfg = Config(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("", response_model=ConfigRead)
def get_config(db: Session = Depends(get_db)):
    return _get_or_create_config(db)


@router.put("", response_model=ConfigRead)
def update_config(body: ConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_or_create_config(db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg
