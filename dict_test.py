'''
Author: Xueao Li @ DUT
Date: 2023-02-12 15:17:34
LastEditors: Xueao Li @ DUT
LastEditTime: 2023-03-27 13:57:50
Description: The description of this script.

'''
#projects = {"default": {"name": "default", "title": 'title','uid_key': 'id','database': 'db','search_template': 'ase/db/templates/search.html','search_template': 'ase/db/templates/search.html','row_template': 'ase/db/templates/row.html','table_template': 'ase/db/templates/table.html'}}
#print(projects["default"])

from ase.db import connect

db = connect("As.db")

for row in db.select():
    db.update(row.id, similarity="[1,2,3]")

