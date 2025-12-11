import json
import re
import mysql.connector

with open ("./taipei-attractions.json", 'r', encoding='utf-8') as file:
    raw = json.load(file)
data = raw["result"]["results"]

con = mysql.connector.connect(
  host = "localhost",
  user = "appuser",
  password = "apppasword",
  database = "tpidaytrip"
)

cursor = con.cursor()

sql_query_att = """
    INSERT INTO attractions 
    (name, category, description, address, transport, mrt, lat, lng)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""
sql_query_img = """
    INSERT INTO images 
    (attraction_id, image_url)
    VALUES (%s, %s)
"""
pattern = r'https?://.*?\.(?:jpg|JPG|png|PNG)'

for attraction in data:
    values_att = (
        attraction["name"],
        attraction["CAT"],
        attraction["description"],
        attraction["address"],
        attraction["direction"],
        attraction["MRT"] if attraction["MRT"] else None,
        float(attraction["latitude"]),
        float(attraction["longitude"]),
    )
    cursor.execute(sql_query_att, values_att)

    att_id = cursor.lastrowid
    image_urls = re.findall(pattern, attraction["file"])
    for url in image_urls:
        cursor.execute(sql_query_img, (att_id, url))

con.commit()
cursor.close()
con.close()
