from fastapi import APIRouter, Depends, HTTPException
from app.auth.middleware import get_current_user
from app.auth.models import UserPermissions

router = APIRouter()

@router.post("/permissions/resolve", summary="Resolve permitted functions", tags=["Permissions"])
async def resolve_permissions(user: UserPermissions = Depends(get_current_user)):
    """Return the list of function names the authenticated user may invoke.
    Designed for internal use by the auth issuer during login.
    """
    if user.permitted_functions is None:
        raise HTTPException(status_code=500, detail="Permission resolution failed")
    return {
        "user_id": user.user_id,
        "permitted_functions": user.permitted_functions,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None
    } 