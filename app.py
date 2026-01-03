from fastapi import *
from fastapi.responses import FileResponse

from typing import Annotated, Optional
from fastapi import  Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from datetime import datetime, timedelta, timezone
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr


SECRET_KEY = "7055ee2f868069730fb6f4e9feb28b80715528b9dcf56e2c799781f728086f92"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

class SignUpIn(BaseModel):
    name: str
    email: EmailStr
    password: str

class SignIn(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str

class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr

password_hasher = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


import mysql.connector
from mysql.connector import pooling
from mysql.connector import Error

dbconfig = {
  "host":"localhost",
  "user":"appuser",
  "password":"apppasword",
  "database":"tpidaytrip",
}

cnxpool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=10,
    pool_reset_session=True,
    **dbconfig
)


# Static Pages (Never Modify Code in this Block)
@app.get("/", include_in_schema=False)
async def index(request: Request):
    return FileResponse("./static/index.html", media_type="text/html")
@app.get("/attraction/{id}", include_in_schema=False)
async def attraction(request: Request, id: int):
    return FileResponse("./static/attraction.html", media_type="text/html")
@app.get("/booking", include_in_schema=False)
async def booking(request: Request):
    return FileResponse("./static/booking.html", media_type="text/html")
@app.get("/thankyou", include_in_schema=False)
async def thankyou(request: Request):
    return FileResponse("./static/thankyou.html", media_type="text/html")


def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return password_hasher.verify(plain_password, password_hash)

def db_get_user_by_email(email: str):
    conn = cnxpool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT id, name, email, password_hash
            FROM member
            WHERE email = %s
        """
        cursor.execute(sql, (email,))
        user = cursor.fetchone()
        return user
    finally:
        cursor.close()
        conn.close()

def db_get_user_by_id(user_id: int):
    conn = cnxpool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT id, name, email
            FROM member
            WHERE id = %s
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
        return user
    finally:
        cursor.close()
        conn.close()

def db_create_user(name: str, email: str, password_hash: str):
    conn = cnxpool.get_connection()
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO member (name, email, password_hash)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (name, email, password_hash))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def create_access_token(*, user_id: int, expires_delta: Optional[timedelta] = None):
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Missing sub")
    return int(sub)


def get_bearer_token_from_header(request: Request):
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    prefix = "Bearer "
    if not auth.startswith(prefix):
        return None
    return auth[len(prefix):].strip() or None

async def get_current_user_optional(request: Request):
    token = get_bearer_token_from_header(request)
    if not token:
        return None

    try:
        user_id = decode_token(token)
    except (InvalidTokenError, ValueError):
        return None

    user = db_get_user_by_id(user_id)
    return user


@app.post("/api/user")
async def sign_up(payload: SignUpIn):
    try:
        if db_get_user_by_email(payload.email):
            raise HTTPException(status_code=400, detail="Email address already in use")

        pwd_hash = hash_password(payload.password)
        db_create_user(payload.name, payload.email, pwd_hash)
        return {"ok": True}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/api/user/auth")
async def sign_in(payload: SignIn):
    try:
        user = db_get_user_by_email(payload.email)
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        if not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        token = create_access_token(user_id=user["id"], expires_delta=timedelta(days=7))
        return {"token": token}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/api/user/auth")
async def get_auth(
    current_user: Annotated[Optional[dict], Depends(get_current_user_optional)]
):
    try:
        if not current_user:
            return {"data": None}

        return {
            "data": {
                "id": current_user["id"],
                "name": current_user["name"],
                "email": current_user["email"],
            }
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


# attractions query
@app.get("/api/attractions")
async def searchquery(
    page: Annotated[int, Query(ge=0)] = 0,
    category: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query()] = None
    ):
    try:
        con = cnxpool.get_connection()
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    try:
        cursor = con.cursor(dictionary=True)

        pageStart = page * 8

        sql = "SELECT * FROM attractions WHERE 1=1"
        params = []

        if category:
            sql += " AND category = %s"
            params.append(category)

        if keyword:
            sql += " AND (mrt = %s OR name LIKE %s)"
            params.extend([keyword, "%" + keyword + "%"])

        sql += " LIMIT 8 OFFSET %s"
        params.append(pageStart)

        cursor.execute(sql, params)
        result = cursor.fetchall()

        if not result:
            return {
                "nextPage": None,
                "data": result
                }

        # if page > 0 and len(result) == 0:
        #     raise HTTPException(status_code=500, detail="Page number out of range")
        # if category and len(result) == 0:
        #     raise HTTPException(status_code=500, detail="Invalid category value")
        # if keyword and len(result) == 0:
        #     raise HTTPException(status_code=500, detail=f"No results found matching '{keyword}'")

        id_list = [item["id"] for item in result]
        

        placeholders = ', '.join(['%s'] * len(id_list))
        sql_img = f"""
            SELECT images.attraction_id, images.image_url
            FROM images
            WHERE images.attraction_id IN ({placeholders});
        """
        cursor.execute(sql_img, tuple(id_list))
        result_img = cursor.fetchall()

        urlMap = {}
        for item in result_img:
            if item["attraction_id"] not in urlMap:
                urlMap[item["attraction_id"]] = []
            urlMap[item["attraction_id"]].append(item["image_url"])

        for item in result:
            item["images"] = urlMap.get(item["id"],[])

        nextPage = page + 1 if len(result) == 8 else None

        return {
            "nextPage": nextPage,
            "data": result
        }

    # except HTTPException as e:
    #     raise e

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    finally:
        if cursor: cursor.close()
        if con and con.is_connected(): con.close()


# attraction id
@app.get("/api/attraction/{attractionId}")
async def searchid(attractionId: int):
    try:
        con = cnxpool.get_connection()
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        cursor = con.cursor(dictionary=True)
        cursor.execute("""
                    SELECT * FROM attractions WHERE id=%s
                    """, (attractionId,))
        result = cursor.fetchone()

        if not result:
            return {"data": result}

        cursor.execute("""
                    SELECT images.image_url
                    FROM attractions
                    JOIN images on images.attraction_id = attractions.id
                    WHERE attractions.id = %s;
                    """, (attractionId,))
        result_img = cursor.fetchall()
        
        imgurl_list = []
        for url in result_img:
            imgurl_list.append(url["image_url"])
        result["image"]=imgurl_list

        return {"data": result}

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    finally:
        cursor.close()
        con.close()

# categories
@app.get("/api/categories")
async def categories():
    try:
        con = cnxpool.get_connection()
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        cursor = con.cursor(dictionary=True)
        cursor.execute("""
                        SELECT DISTINCT category
                        FROM attractions;
                        """,)
        result = cursor.fetchall()

        result_list = []
        for item in result:
            result_list.append(item["category"])
        return {"data": result_list}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        cursor.close()
        con.close()

# mrt order
@app.get("/api/mrts")
async def mrts():
    try:
        con = cnxpool.get_connection()
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection error")
    
    try:
        cursor = con.cursor(dictionary=True)
        cursor.execute("""
                    SELECT mrt
                    FROM (
                        SELECT mrt, COUNT(*) AS mrt_count
                        FROM attractions
                        GROUP BY mrt)
                    AS mrt_only
                    ORDER BY mrt_count DESC;
                    """,)
        result = cursor.fetchall()

        result_list = []
        for item in result:
            result_list.append(item["mrt"])
        return {"data": result_list}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        cursor.close()
        con.close()

# error handle
@app.exception_handler(HTTPException)
async def exeption_handler(request:Request, exc:Exception):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True, 
            "message": exc.detail
            },
    )

@app.exception_handler(RequestValidationError)
async def exeption_handler(request:Request, exc:RequestValidationError):  
    # print(exc.errors()) 
    return JSONResponse(
       status_code=400,
        content={
            "error": True,
            "message": exc.errors()[0].get("msg")
        }
    )