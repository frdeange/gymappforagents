from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from jose import jwt, JWTError
from backend.models.mod_auth import AuthUser, UserRole, TokenData
from backend.configuration.config import Config
import httpx
from datetime import datetime
from functools import lru_cache

# # OAuth2 configuration for Microsoft Entra External ID using OAuth2 Authorization Code Flow
# oauth2_scheme = OAuth2AuthorizationCodeBearer(
#     authorizationUrl=f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.b2clogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/oauth2/v2.0/authorize",
#     tokenUrl=f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.b2clogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/oauth2/v2.0/token"
# )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@lru_cache(maxsize=1)
async def get_jwks():
    """
    Fetch and cache the JSON Web Key Set (JWKS) from Microsoft Entra External ID.
    The JWKS contains the public keys used to verify the JWT tokens.
    """
    jwks_uri = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.b2clogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_uri)
        return response.json()

async def get_key(kid: str):
    """Get the public key matching the key ID from the JWKS"""
    jwks = await get_jwks()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to verify credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def verify_token(token: str) -> TokenData:
    """
    Verify the JWT token and extract its claims.
    Raises HTTPException if token is invalid.
    """
    try:
        # Get the header without verifying the token
        header = jwt.get_unverified_header(token)
        # Get the key used to sign this token
        key = await get_key(header["kid"])
        # Construct issuer URL dynamically
        issuer = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.b2clogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/v2.0/"
        # Verify the token and get its claims
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=Config.AZURE_ENTRAID_CLIENT_ID,
            issuer=issuer
        )
        # Extract relevant claims
        token_data = TokenData(
            id=payload.get("oid"),  # Object ID from Entra External ID
            email=payload.get("email"),
            name=payload.get("name"),
            role=payload.get("roles", ["user"])[0],  # Default to user role if none specified
            exp=payload.get("exp"),
            original_token=token  # Guardar el token original
        )
        # Verify token expiration
        if token_data.exp and datetime.utcnow().timestamp() > token_data.exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme)) -> AuthUser:
    """
    Get the current authenticated user from the token.
    This is the main dependency to be used in protected endpoints.
    """
    token_data = await verify_token(token)
    # TODO: Fetch additional user data from database if needed
    # For now, we'll create the AuthUser from token data
    user = AuthUser(
        id=token_data.id,
        email=token_data.email,
        name=token_data.name,
        role=token_data.role
    )
    return user

def get_current_user_id(current_user: AuthUser = Depends(get_current_user)) -> str:
    """Get just the user ID from the current authenticated user"""
    return current_user.id

def get_current_admin(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency for endpoints that require admin access"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action"
        )
    return current_user

def get_current_trainer(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency for endpoints that require trainer access"""
    if current_user.role not in [UserRole.TRAINER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action"
        )
    return current_user