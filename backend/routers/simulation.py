from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from services.ff_engine import fast_forward

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/fastforward")
def ff(body: dict, db: Session = Depends(get_db)):
    try:
        return fast_forward(
            game_id=body["game_id"],
            days=int(body["days"]),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing field: {e}")