from dataServer import app
from flask import render_template, g, jsonify, request
#import MySQLdb
import mysql.connector as MySQLdb
import gviz_api
from datetime import datetime
from dateutil import tz

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

def appendFracSec(dataMat, sCol, fsCol, idCol):
    entries = len(dataMat)
    fSecs = [ float(dataMat[idx][fsCol])/(2**32) for idx in xrange(entries) ]

    dOut = []
    for i in range(len(dataMat[0])):
        if (i != sCol) and (i != fsCol) and ( i != idCol ):
            dOut.append([ dataMat[idx][i] for idx in xrange(entries) ])
        if i == sCol:
            dOut.append([ datetime.fromtimestamp(dataMat[idx][i] + fSecs[idx]) for idx in xrange(entries) ])

    # return transpose
    return map(list, zip(*dOut))


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

@app.route('/table/<tableName>/')
def showTable(tableName=None):
    db = get_db()
    table = tableNameFormatter(tableName) # use simple name in url
    if not checkDbTableExists(db, table):
        return redirect(url_for('showTables'))

    cur = db.cursor()
    #query = """SELECT * FROM {0} ORDER BY id DESC LIMIT 600""".format(table)
    query = """SELECT measurementTime,fts,c8,c9,c10,c11,c12,c13,id FROM {0} ORDER BY
        id DESC LIMIT 1000""".format(table)
    cur.execute(query)
    rows=cur.fetchall()

    cnt = 0
    SecCol = None
    fracSecCol = None
    field_names = []
    for i in cur.description:
        if not (i[0] in ['id', 'fts']):
            field_names.append(i[0])
        elif i[0] == 'fts':
            fracSecCol = cnt
        elif i[0] == 'id':
            idCol = cnt
            firstID = rows[-1][cnt]
            lastID = rows[0][cnt]
            if lastID < firstID:
                temp = lastID
                lastID = firstID
                firstID = temp
        if i[0] == 'measurementTime':
            SecCol = cnt
        cnt += 1
    cur.close()
            
    # could be problem if fts is defined and measurementTime is not
    if ( SecCol != None ) and ( fracSecCol != None ):
        rows = appendFracSec(map(list, rows), SecCol, fracSecCol, idCol)

    data = [",".join(field_names)]
    for r in rows:
        data.append(",".join(map(str,r)))
    
    return render_template('tableDataDY_csv.html', data="\n".join(data), tableName=tableName,
            idRange=[firstID, lastID])

@app.route('/newData/<table>/')
def getNewData(table=None):
    lastID = request.args.get('lastID', -1, type=int)
    if lastID < 0:
        return ('', 204)

    db = get_db()
    table = tableNameFormatter(table) # use simple name in url
    if not checkDbTableExists(db, table):
        return ('', 204)

    cur = db.cursor()
    query = """SELECT measurementTime,fts,c8,c9,c10,c11,c12,c13,id FROM {}
    WHERE id > {} ORDER BY id DESC""".format(table, lastID)
    print query
    cur.execute(query)
    rows=cur.fetchall()
    print len(rows)

    cnt = 0
    SecCol = None
    fracSecCol = None
    field_names = []
    try:
        for i in cur.description:
            if not (i[0] in ['id', 'fts']):
                field_names.append(i[0])
            elif i[0] == 'fts':
                fracSecCol = cnt
            elif i[0] == 'id':
                firstID = rows[-1][cnt]
                lastID = rows[0][cnt]
                if lastID < firstID:
                    temp = lastID
                    lastID = firstID
                    firstID = temp
                idCol = cnt
            if i[0] == 'measurementTime':
                SecCol = cnt
            cnt += 1
    except IndexError:
        # there are no new entries
        cur.close()
        return ('', 204)

    cur.close()
            
    # could be problem if fts is defined and measurementTime is not
    if ( SecCol != None ) and ( fracSecCol != None ):
        rows = appendFracSec(map(list, rows), SecCol, fracSecCol, idCol)

    data = []
    for r in rows:
        data.append(",".join(map(str,r)))
    
    #print data
    return jsonify(dataStr="\n".join(data), lastID=lastID)

@app.route('/ntpCheck')
def ntpCheck():
    db = get_db()
    table = tableNameFormatter("ntpTest3") # use simple name in url
    if not checkDbTableExists(db, table):
        return redirect(url_for('showTables'))

    cur = db.cursor()
    #query = """SELECT * FROM {0} ORDER BY id DESC LIMIT 600""".format(table)
    query = """SELECT measurementTime,c0 FROM {0} ORDER BY
    id DESC LIMIT 1000""".format(table)
    cur.execute(query)
    rows=cur.fetchall()

    local_tz = tz.tzlocal()
    rows = [ [datetime.fromtimestamp(r[0], local_tz), r[1]] for r in rows ]

    field_names = []
    for i in cur.description:
        if i[0] != 'id':
            field_names.append(i[0])

#    desc = dict([ (i, ("number", i)) for i in field_names ])
    desc_list = []
    for i in field_names:
        if i == "measurementTime":
            desc_list.append( (i, ("datetime", i)) )
        else:
            desc_list.append( (i, ("number", i)) )
    desc = dict(desc_list)

    cur.close()
    print desc
    print field_names

    data = [ dict( zip(field_names,r) ) for r in rows ]
    data_table = gviz_api.DataTable(desc)
    data_table.LoadData(data)
    json = data_table.ToJSon(columns_order=tuple(field_names),order_by=field_names[0])
    
    #return json
    return render_template('tableData.html', data=json)
