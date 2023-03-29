"""WSGI Flask-app for browsing a database.

::

    +---------------------+
    | layout.html         |
    | +-----------------+ |    +--------------+
    | | search.html     | |    | layout.html  |
    | |     +           | |    | +---------+  |
    | | table.html ----------->| |row.html |  |
    | |                 | |    | +---------+  |
    | +-----------------+ |    +--------------+
    +---------------------+

You can launch Flask's local webserver like this::

    $ ase db abc.db -w

or this::

    $ python3 -m ase.db.app abc.db

"""

import io
import sys
from typing import Dict, Any, Set
from pathlib import Path

from flask import Flask, render_template, request

from ase.db import connect
from ase.db.core import Database
from ase.formula import Formula
#from ase.db.web import create_key_descriptions, Session
from web import create_key_descriptions, Session

from ase.db.row import row2dct, AtomsRow
from ase.db.table import all_columns
import os

root = Path(__file__).parent.parent.parent
app = Flask(__name__, template_folder=str(root))

projects: Dict[str, Dict[str, Any]] = {}

@app.route('/', defaults={'project_name': 'default'})
@app.route('/<project_name>')
@app.route('/<project_name>/')
def search(project_name: str):

    """Search page.

    Contains input form for database query and a table result rows.
    """
    if project_name == 'favicon.ico':
        return '', 204, []  # 204: "No content"
    session = Session(project_name)
    #print(project_name)
    project = projects[project_name]
    return render_template(project['search_template'],
                           q=request.args.get('query', ''),
                           p=project,
                           session_id=session.id)


@app.route('/update/<int:sid>/<what>/<x>/')
def update(sid: int, what: str, x: str):
    """Update table of rows inside search page.

    ``what`` must be one of:

    * query: execute query in request.args (x not used)
    * limit: set number of rows to show to x
    * toggle: toggle column x
    * sort: sort after column x
    * page: show page x
    """


    session = Session.get(sid)
    project = projects[session.project_name]
    session.update(what, x, request.args, project)
    table = session.create_table(project['database'],
                                 project['uid_key'],
                                 keys=list(project['key_descriptions']))
    return render_template(project['table_template'],
                           t=table,
                           p=project,
                           s=session)


#from flask import send_from_directory
# #尝试给标签页加图标，失败了。
#@app.route('/favicon.ico')
#def favicon():
#    print(os.path.join(app.root_path, 'static'))
#    return send_from_directory(os.path.join(app.root_path, 'static'),
#                               'favicon.ico', mimetype='images/favicon.ico')
#    #return app.send_static_file('images/favicon.ico')

@app.route('/<project_name>/row/<uid>')
def row(project_name: str, uid: str):
    """Show details for one database row."""

    def str2list(text):
        '''把字符串转换成列表。
        如把 "[[1,2,3],[4,5,6]]" 转换成 [[1,2,3],[4,5,6]] '''
        import ast
        import re
        text = text.replace(",", " ")
        text = text.replace('\n', '')
        xs = re.sub('\s+', ',', text)
        list1 = ast.literal_eval(xs)
        return list1

    def extract_elements(s):
        import re
        # 找到所有的元素及其数量
        elements = re.findall(r'([A-Z][a-z]*)(?:<sub>(\d+)</sub>)?', s)
        # 将元素按照字母表顺序排序
        sorted_elements = sorted(elements, key=lambda x: x[0])
        # 将元素名称拼接起来
        element_names = [e[0] for e in sorted_elements]
        result = ''.join(element_names)
        return result

    project = projects[project_name]
    uid_key = project['uid_key']
    row = project['database'].get('{uid_key}={uid}'
                                  .format(uid_key=uid_key, uid=uid))
    dct = project['row_to_dict_function'](row, project)
    Physical_list = ["HOMO_DFT","LUMO_DFT","GAP_DFT","HOMO_GW","LUMO_GW","GAP_GW","natoms","formula"\
        ,"Point_Group","Cluster_type"]
    Technical_list = ["Reference","Max_Force","TOTEN","Functional","user","ctime","id","unique_id"\
        ,"filename","relaxed","pbc","calculator_relaxation","calculator_GW"]

    element = extract_elements(dct['formula']) # 这个方法暂时这么用，以后需要改。

    type_ = None
    simlarity_id_list, simlarity_val_list = [],[]
    for key, desc, vals in dct['table']:
        if key == "Cluster_type":
            type_ = vals
        if key == "similarity_id":
            simlarity_id_list = str2list(vals)
        if key == "similarity_val":
            simlarity_val_list = str2list(vals)

    simi_list = [("None", "None")]
    if simlarity_id_list:
        simi_list = list(zip(simlarity_id_list, simlarity_val_list))        

    dos_dir = ''
    if type_:
        dos_dir = type_+'/'+element #团簇类型/元素（多元团簇时可能有问题）       

    return render_template(project['row_template'],
                           d=dct, row=row, p=project, uid=uid, list1=Physical_list, list2=Technical_list,
                           dos_dir=dos_dir, simi_list = simi_list) 


@app.route('/atoms/<project_name>/<int:id>/<type>')
def atoms(project_name: str, id: int, type: str):
    """Return atomic structure as cif, xyz or json."""
    row = projects[project_name]['database'].get(id=id)
    a = row.toatoms()
    if type == 'cif':
        b = io.BytesIO()
        a.pbc = True
        a.write(b, 'cif', wrap=False)
        return b.getvalue(), 200, []

    fd = io.StringIO()
    if type == 'xyz':
        a.write(fd, 'xyz')
    elif type == 'json':
        con = connect(fd, type='json')
        con.write(row,
                  data=row.get('data', {}),
                  **row.get('key_value_pairs', {}))
    else:
        1 / 0

    headers = [('Content-Disposition',
                'attachment; filename="{project_name}-{id}.{type}"'
                .format(project_name=project_name, id=id, type=type))]
    txt = fd.getvalue()
    return txt, 200, headers


@app.route('/gui/<int:id>')
def gui(id: int):
    """Pop ud ase gui window."""
    from ase.visualize import view
    atoms = projects['default']['database'].get_atoms(id)
    view(atoms)
    return '', 204, []


@app.route('/lxashuai')
def test():
    return render_template("ase/db/templates/cd.html")

@app.route('/robots.txt')
def robots():
    return ('User-agent: *\n'
            'Disallow: /\n'
            '\n'
            'User-agent: Baiduspider\n'
            'Disallow: /\n'
            '\n'
            'User-agent: SiteCheck-sitecrawl by Siteimprove.com\n'
            'Disallow: /\n',
            200)


def handle_query(args) -> str:
    """Converts request args to ase.db query string."""
    return args['query']


def row_to_dict(row: AtomsRow, project: Dict[str, Any]) -> Dict[str, Any]:
    """Convert row to dict for use in html template."""
    dct = row2dct(row, project['key_descriptions'])
    dct['formula'] = Formula(Formula(row.formula).format('abc')).format('html')
    return dct


def add_project(db: Database) -> None:
    """Add database to projects with name 'default'."""
    all_keys: Set[str] = set()
    for row in db.select(columns=['key_value_pairs'], include_data=False):
        all_keys.update(row._keys)

    key_descriptions = {key: (key, '', '') for key in all_keys}

    meta: Dict[str, Any] = db.metadata

    if 'key_descriptions' in meta:
        key_descriptions.update(meta['key_descriptions'])

    default_columns = meta.get('default_columns')
    if default_columns is None:
        default_columns = all_columns[:]

    projects['default'] = {
        'name': 'default',
        'title': meta.get('title', ''),
        'uid_key': 'id',
        'key_descriptions': create_key_descriptions(key_descriptions),
        'database': db,
        'row_to_dict_function': row_to_dict,
        'handle_query_function': handle_query,
        'default_columns': default_columns,
        'search_template': 'ase/db/templates/search.html',
        'row_template': 'ase/db/templates/row.html',
        'table_template': 'ase/db/templates/table.html',
        "test_template": 'ase/db/templates/test.html'}

#print(projects)
#db = connect(r"/root/aseDB_flask/ase/db/DATABASE.db")
db = connect("DATABASE.db")
#db = connect("As.db")
add_project(db)

if __name__ == '__main__':
    #db = connect(sys.argv[1])
    #app.run(host='0.0.0.0',port=8886, debug=True)
    app.run(host='0.0.0.0',port=8001, debug=True)
