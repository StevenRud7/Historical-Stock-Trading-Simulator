from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from services.portfolio_service import execute_trade, get_portfolio_snapshot, get_trade_history

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("/trade")
def trade(body: dict, db: Session = Depends(get_db)):
    try:
        return execute_trade(
            game_id=body["game_id"],
            ticker=body["ticker"],
            action=body["action"],
            quantity=float(body["quantity"]),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing field: {e}")


@router.get("/{game_id}")
def portfolio(game_id: str, db: Session = Depends(get_db)):
    try:
        return get_portfolio_snapshot(game_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{game_id}/history")
def trade_history(game_id: str, db: Session = Depends(get_db)):
    return get_trade_history(game_id, db)