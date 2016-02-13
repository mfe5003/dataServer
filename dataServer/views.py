from dataServer import app
from flask import render_template, g, jsonify
import MySQLdb
import gviz_api

def connect_db():
    """Connect to the application database"""
    return MySQLdb.connect(
        host=app.config['DB_HOST'],
        db=app.config['DATABASE'],
        user=app.config['USERNAME'],
        passwd=app.config['PASSWORD']
    )

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'mysql_db'):
        g.mysql_db = connect_db()
    return g.mysql_db

def checkDbTableExists(dbcon, tablename):
    cur = dbcon.cursor()
    query = """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = %s
     """
    cur.execute(query, (tablename,))
    if cur.fetchone()[0] == 1:
        cur.close()
        return True
     
    cur.close()
    return False

def tableNameFormatter(table):
    return 'measurements_'+table

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'mysql_db'):
        g.mysql_db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/showTables/')
def showTables():
    db = get_db()
    cur = db.cursor()
    query = "SHOW TABLES"
    cur.execute(query)
    rv = cur.fetchall()
    return str(rv)

@app.route('/table/<table>/')
def showTable(table=None):
    db = get_db()
    table = tableNameFormatter(table) # use simple name in url
    if not checkDbTableExists(db, table):
        return redirect(url_for('showTables'))

    cur = db.cursor()
    query = """SELECT * FROM {0} ORDER BY id DESC LIMIT 600""".format(table)
    cur.execute(query)
    rows=cur.fetchall()

    field_names = []
    for i in cur.description:
        if i[0] != 'id':
            field_names.append(i[0])

    desc = dict([ (i, ("number", i)) for i in field_names ])

    cur.close()
    print desc
    print field_names

    data = [ dict( zip(field_names,r) ) for r in rows ]
    data_table = gviz_api.DataTable(desc)
    data_table.LoadData(data)
    json = data_table.ToJSon(columns_order=tuple(field_names),order_by=field_names[0])
    
    #return json
    return render_template('tableData.html', data=json)
