from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from services import game_engine
from services.portfolio_service import get_end_game_summary

router = APIRouter(prefix="/api/game", tags=["game"])


@router.post("/new")
def create_game(config: dict, db: Session = Depends(get_db)):
    try:
        return game_engine.create_game(config, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create game: {str(e)}")


@router.get("/{game_id}")
def get_game(game_id: str, db: Session = Depends(get_db)):
    result = game_engine.get_game(game_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Game not found")
    return result


@router.post("/{game_id}/advance")
def advance_day(game_id: str, db: Session = Depends(get_db)):
    try:
        return game_engine.advance_day(game_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/quit")
def quit_game(game_id: str, db: Session = Depends(get_db)):
    """Mark game as quit_early and return final summary."""
    from db.database import GameSession
    game = db.query(GameSession).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status == "active":
        game.status = "quit_early"
        db.commit()
    try:
        return get_end_game_summary(game_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{game_id}/summary")
def end_game_summary(game_id: str, db: Session = Depends(get_db)):
    try:
        return get_end_game_summary(game_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))