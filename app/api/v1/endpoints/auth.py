"""Authentication endpoints (login / signup / refresh / me / change-password)."""

from fastapi import APIRouter, Depends, status

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.serializers import user_session

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new business account",
)
def signup(payload: SignupRequest, services: AppServices = Depends(get_services)) -> dict:
    return services.auth.signup(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
        district=payload.district,
        business_name=payload.business_name,
    )


@router.post("/register", response_model=TokenResponse, include_in_schema=False)
def register(payload: SignupRequest, services: AppServices = Depends(get_services)) -> dict:
    """Alias of signup."""
    return services.auth.signup(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
        district=payload.district,
        business_name=payload.business_name,
    )


@router.post("/login", response_model=TokenResponse, summary="Login with email and password")
def login(payload: LoginRequest, services: AppServices = Depends(get_services)) -> dict:
    return services.auth.login(email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenResponse, summary="Exchange a refresh token for a new access token")
def refresh(payload: RefreshRequest, services: AppServices = Depends(get_services)) -> dict:
    return services.auth.refresh(refresh_token=payload.refresh_token)


@router.get("/me", response_model=dict, summary="Current authenticated user")
def me(user: User = Depends(get_current_user)) -> dict:
    return user_session(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> None:
    services.auth.change_password(user=user, old_password=payload.old_password, new_password=payload.new_password)