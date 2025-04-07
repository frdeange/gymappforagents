from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from jose import jwt, JWTError
from backend.models.mod_auth import AuthUser, UserRole, AuthTokenData
from backend.configuration.config import Config
import httpx
from datetime import datetime
from functools import lru_cache
import json
from backend.configuration.monitor import log_exception
import logging
import json
from jose import jwt, jwk
from jose.utils import base64url_decode
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import httpx
from fastapi import HTTPException, status
import base64


_jwks_cache = None
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_jwks():
    """
    Fetch and cache the JSON Web Key Set (JWKS) from Microsoft Entra External ID.
    The JWKS contains the public keys used to verify the JWT tokens.
    """
    global _jwks_cache

    if _jwks_cache is not None:
        return _jwks_cache

    jwks_uri = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/discovery/v2.0/keys"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_uri, timeout=10.0)

            if response.status_code != 200:
                log_exception(
                    Exception(f"JWKS endpoint returned non-200 status: {response.status_code}"),
                    {"uri": jwks_uri, "response_text": response.text}
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error fetching JWT keys: Status {response.status_code}"
                )

            try:
                _jwks_cache = response.json()  # Saving cache
                return _jwks_cache
            except json.JSONDecodeError as e:
                log_exception(e, {"uri": jwks_uri, "response_text": response.text[:500]})
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid JSON response from key server"
                )
    except httpx.RequestError as e:
        log_exception(e, {"uri": jwks_uri})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to key server: {str(e)}"
        )

async def get_key(kid: str):
    """Get the public key matching the key ID from the JWKS"""
    try:
        jwks = await get_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        
        # Key not found in JWKS
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signing key not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        log_exception(e, {"kid": kid})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing authentication keys"
        )

async def verify_auth_token(token) -> AuthTokenData:
    """
    Verify the JWT auth token by validating issuer, audience, algorithm, and key ID (kid).
    Signature validation is skipped.
    """
    try:
        # This is to validate ID_token expected_issuer = "https://" + Config.AZURE_ENTRAID_TENANT_ID + ".ciamlogin.com/" + Config.AZURE_ENTRAID_TENANT_ID + "/v2.0"
        expected_issuer = Config.AZURE_ENTRAID_ACCESSTOKEN_ISSUER + Config.AZURE_ENTRAID_TENANT_ID + "/"
        expected_audience = Config.AZURE_ENTRAID_AUDIENCE
        expected_alg = Config.JWT_ALGORITHM
                               
        # Extract claims and header using jose.jwt
        unverified_claims = jwt.get_unverified_claims(token)
        unverified_header = jwt.get_unverified_header(token)

        # Validate token expiration
        if unverified_claims.get("exp") < datetime.utcnow().timestamp():
            raise HTTPException(status_code=401, detail="Invalid token: expired")

        # Validate algorithm
        if unverified_header.get("alg") != expected_alg:
            raise HTTPException(status_code=401, detail="Invalid token: algorithm mismatch")

        # Validate issuer
        if unverified_claims.get("iss") != expected_issuer:
            raise HTTPException(status_code=401, detail="Invalid token: issuer mismatch")

        # Validate audience
        if unverified_claims.get("aud") != expected_audience:
            raise HTTPException(status_code=401, detail="Invalid token: audience mismatch")

        # Validate that token has kid item and it's in the jwks
        if unverified_header.get("kid") is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing key ID")

        if await get_key(unverified_header.get("kid")) is None:
            raise HTTPException(status_code=401, detail="Invalid token: key ID not found in JWKS")       
        
        # Return token data if all validations pass
        token_data = AuthTokenData(
            id=unverified_claims.get("oid"),
            email=unverified_claims.get("unique_name"),
            name=unverified_claims.get("name"),
            userGivenName=unverified_claims.get("given_name", ""),
            userLastName=unverified_claims.get("family_name", ""),
            role=unverified_claims.get("idtyp"),
            exp=unverified_claims.get("exp"),
            original_token=token
)
        return token_data

    except (ValueError, KeyError, JWTError) as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

async def verify_id_token(token) -> AuthUser:
    """
    Verify the JWT Identity token by validating issuer, audience, algorithm, and key ID (kid).
    Signature validation is skipped.
    """
    try:
        expected_issuer = "https://" + Config.AZURE_ENTRAID_TENANT_ID + ".ciamlogin.com/" + Config.AZURE_ENTRAID_TENANT_ID + "/v2.0"
        expected_audience = Config.AZURE_ENTRAID_CLIENT_ID
        expected_alg = Config.JWT_ALGORITHM
                               
        # Extract claims and header using jose.jwt
        unverified_claims = jwt.get_unverified_claims(token)
        unverified_header = jwt.get_unverified_header(token)

        # Validate token expiration
        if unverified_claims.get("exp") < datetime.utcnow().timestamp():
            raise HTTPException(status_code=401, detail="Invalid token: expired")

        # Validate algorithm
        if unverified_header.get("alg") != expected_alg:
            raise HTTPException(status_code=401, detail="Invalid token: algorithm mismatch")

        # Validate issuer
        if unverified_claims.get("iss") != expected_issuer:
            raise HTTPException(status_code=401, detail="Invalid token: issuer mismatch")

        # Validate audience
        if unverified_claims.get("aud") != expected_audience:
            raise HTTPException(status_code=401, detail="Invalid token: audience mismatch")

        # Validate that token has kid item and it's in the jwks
        if unverified_header.get("kid") is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing key ID")

        if await get_key(unverified_header.get("kid")) is None:
            raise HTTPException(status_code=401, detail="Invalid token: key ID not found in JWKS")

        # Verify the token signature using jwt.decode
        if jwt.decode(
            token, 
            await get_key(unverified_header.get("kid")), 
            algorithms=[expected_alg], 
            audience=expected_audience, 
            issuer=expected_issuer
            ) is None:
            raise HTTPException(status_code=401, detail="Invalid token: signature mismatch")  
              
        # Return id_token data if all validations pass
        token_data = AuthUser(
            id=unverified_claims.get("oid"),
            email=unverified_claims.get("email"),
            Fullname=unverified_claims.get("name"),
            name=unverified_claims.get("given_name", ""),
            surName=unverified_claims.get("family_name", ""),
            role=unverified_claims.get("userRole"),
            phone=unverified_claims.get("userPhone"),
            birthday=unverified_claims.get("userBirthday"),
            city=unverified_claims.get("city"),
            streetAddress=unverified_claims.get("userStreetAddress"),
            postalCode=unverified_claims.get("postalCode",""),
            tokenExpiration=unverified_claims.get("exp"),
            original_token=token
)
        return token_data

    except (ValueError, KeyError, JWTError) as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

async def get_current_user(auth_token: str = Depends(oauth2_scheme)) -> AuthTokenData:
    """
    Get the current authenticated user from the access token.
    This is the main dependency to be used in protected endpoints.
    """
    token_data = await verify_auth_token(auth_token)

    # Create a basic AuthUser object from token data
    user = AuthTokenData(
        id=token_data.id,
        email=token_data.email,
        name=token_data.name,
        userGivenName=token_data.userGivenName,
        userLastName=token_data.userLastName,
        role=token_data.role,
        exp=token_data.exp,
        original_token=token_data.original_token
    )

    return user

async def get_user_info(id_token: str) -> AuthUser:
    """
    Extract detailed user information from the ID token.
    """
    try:
        # Decode the ID token to extract claims
        unverified_claims = jwt.get_unverified_claims(id_token)

        # Create an AuthUser object with detailed information
        user = AuthUser(
            id=unverified_claims.get("oid"),
            email=unverified_claims.get("email"),
            name=unverified_claims.get("name"),
            role=unverified_claims.get("idtyp"),
            exp=unverified_claims.get("exp"),
            userGivenName=unverified_claims.get("given_name"),
            userLastName=unverified_claims.get("family_name"),
            phone=unverified_claims.get("userPhone"),
            birthday=unverified_claims.get("userBirthday"),
            street_address=unverified_claims.get("userStreetAddress"),
            city=unverified_claims.get("city"),
            postal_code=unverified_claims.get("postalCode")
        )

        return user
    except Exception as e:
        log_exception(e, {"id_token": id_token})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ID token"
        )

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