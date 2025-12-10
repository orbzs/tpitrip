from fastapi import *
from fastapi.responses import FileResponse

from typing import Annotated
from fastapi import FastAPI, Query

app=FastAPI()

import mysql.connector

con = mysql.connector.connect(
  host="localhost",
  user="root",
  password="mysql",
  database="tpidaytrip"
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


@app.get("/api/attraction/{attractionId}")
async def searchid(attractionId: int):
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
    con.close()
    
    imgurl_list = []
    for url in result_img:
        imgurl_list.append(url["image_url"])
    result["image"]=imgurl_list

    return {"data": result}
