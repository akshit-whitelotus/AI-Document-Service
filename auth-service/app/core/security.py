from __future__ import annotations
import base64,secrets
from datetime import datetime,timedelta,timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,InvalidHashError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from app.core.config import settings

_password_hasher=PasswordHasher()

def hash_password(plain_password:str) -> str :
    return _password_hasher.hash(plain_password)

def verify_password(plain_password:str, hashed_password:str) ->bool:
    try:
        return _password_hasher.verify(hashed_password,plain_password)
    except(VerifyMismatchError,InvalidHashError):
        return False

def needs_rehash(hashed_password:str) -> bool:
    return _password_hasher.check_needs_rehash(hashed_password)


def ensure_keypair_exists() -> None:
    if settings.private_key_path.exists() and settings.public_key_path.exists():
        return
    settings.public_key_path.parent.mkdir(parents=True,exist_ok=True)
    settings.private_key_path.parent.mkdir(parents=True,exist_ok=True)

    private_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)

    private_pem=private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem=private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    settings.private_key_path.write_bytes(private_pem)
    settings.public_key_path.write_bytes(public_pem)

def _load_private_key() -> str :
    ensure_keypair_exists()
    return settings.private_key_path.read_text()

def _load_public_key() -> str:
    ensure_keypair_exists()
    return settings.public_key_path.read_text()


def _b64url_uint(value:int) -> str:
    raw=value.to_bytes((value.bit_length() +7)//8 ,"big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

def get_jwks()->dict:
    ensure_keypair_exists()
    public_key=serialization.load_pem_public_key(settings.public_key_path.read_bytes())
    numbers=public_key.public_numbers()

    return{
        "keys":[
            {
                "kty":"RSA",
                "use":"sig",
                "alg":settings.JWT_ALGORITHM,
                "kid":settings.JWT_KID,
                "n":_b64url_uint(numbers.n),
                "e":_b64url_uint(numbers.e)

            }
        ]
    }

def create_access_token(user_id:str,email:str)-> str:
    now=datetime.now(timezone.utc)
    payload={
        "sub":user_id,
        "email":email,
        "iss":settings.JWT_ISSUER,
        "aud":settings.JWT_AUDIENCE,
        "iat":now,
        "exp":now+timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type":"access"
    }
    return jwt.encode(
        payload,
        _load_private_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid":settings.JWT_KID}
    )

def generate_refresh_token()->str:
    return secrets.token_urlsafe(48)
