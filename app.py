from fastapi import *
from fastapi.responses import FileResponse

from typing import Annotated
from fastapi import  Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app=FastAPI()

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
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")

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

        if page > 0 and len(result) == 0:
            raise HTTPException(status_code=500, detail="Page number out of range")
        if category and len(result) == 0:
            raise HTTPException(status_code=500, detail="Invalid category value")
        if keyword and len(result) == 0:
            raise HTTPException(status_code=500, detail=f"No results found matching '{keyword}'")

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

    except HTTPException as e:
        raise e

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
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")
    
    try:
        cursor = con.cursor(dictionary=True)
        cursor.execute("""
                    SELECT * FROM attractions WHERE id=%s
                    """, (attractionId,))
        result = cursor.fetchone()

        if result == None:
            return {
                "error": True,
                "message": "景點編號不存在"
            }

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
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")
    
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
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")
    finally:
        cursor.close()
        con.close()

# mrt order
@app.get("/api/mrts")
async def mrts():
    try:
        con = cnxpool.get_connection()
    except Exception:
        raise HTTPException(status_code=500, detail="資料庫連線錯誤")
    
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
    if exc.status_code == 500:
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": exc.detail
            }
        )
    raise exc

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