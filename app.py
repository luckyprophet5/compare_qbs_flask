import pandas as pd
import sqlite3
from io import BytesIO
import base64
import matplotlib.pyplot as plt
import pickle
import json
from flask import Flask, request, g, render_template, url_for

app = Flask(__name__)
DATABASE = 'pbp_data.db'
PICKLE_FILE = "passers_by_year.p"

# https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def query_db(query, params=()):
    db = get_db()
    return pd.read_sql_query(query, db, params=params)

def get_qb_plays(qb, year):
    if qb=="Average":
        return query_db("SELECT * FROM play_by_play WHERE season=?", params=(year,))
    return query_db("SELECT * FROM play_by_play WHERE season=? AND (passer=? OR rusher=?)", params=(year, qb, qb))

def qb_profile(qb, year):
    qb_plays = get_qb_plays(qb, year)
    num_plays = len(qb_plays)
    int_score = qb_plays.loc[qb_plays.interception==1].epa.sum()/num_plays
    sack_score = qb_plays.loc[qb_plays.sack==1].epa.sum()/num_plays
    screen_score = qb_plays.loc[(qb_plays.air_yards <= 0)].epa.sum()/num_plays
    short_score = qb_plays.loc[(qb_plays.air_yards > 0) & (qb_plays.air_yards <= 10)].epa.sum()/num_plays
    intermediate_score = qb_plays.loc[(qb_plays.air_yards > 10) & (qb_plays.air_yards <= 20)].epa.sum()/num_plays
    deep_score = qb_plays.loc[(qb_plays.air_yards > 20)].epa.sum()/num_plays
    run_score = qb_plays.loc[(qb_plays.qb_scramble==1) | (qb_plays.rush==1)].epa.sum()/num_plays
    return {
            "Interceptions":int_score, 
            "Sacks":sack_score,
            "Screen passes":screen_score,
            "Short passes":short_score,
            "Intermediate passes":intermediate_score,
            "Deep passes":deep_score,
            "Rushes":run_score,
           }

def qb_string(qb, year):
    return f"'{(year%100):02d} {qb}"

def compare_qbs(qb1, year1, qb2, year2):
    return  {
                qb_string(qb1,year1):qb_profile(qb1,year1),
                qb_string(qb2,year2):qb_profile(qb2,year2)
            }

def plot_qb_comparison(scores):
    fig = pd.DataFrame(scores).plot(kind='bar').get_figure()
    plt.ylabel('EPA/total # plays')
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    buffer = b''.join(buf)
    b2 = base64.b64encode(buffer)
    fig2 = b2.decode('utf-8')
    qb1_str = list(scores.keys())[0]
    qb2_str = qb1_str
    if len(scores.keys()) > 1:
        qb2_str = list(scores.keys())[1]
    return fig2, qb1_str, qb2_str

@app.route('/', methods=['GET'])
def home():
    args_present = True
    passers_by_year = pickle.load(open(PICKLE_FILE, "rb"))

    for arg in ['qb1', 'year1', 'qb2', 'year2']:
        if arg not in request.args:
            args_present = False
            break
    if args_present:
        qb1 = request.args['qb1']
        year1 = int(request.args['year1'])
        qb2 = request.args['qb2']
        year2 = int(request.args['year2'])
        scores = compare_qbs(qb1, year1, qb2, year2)
        fig, qb1_str, qb2_str = plot_qb_comparison(scores)
        return render_template('compare_qbs.html', fig=fig, qb1_str=qb1_str, qb2_str=qb2_str, passers_by_year=json.dumps(passers_by_year), has_fig=True)
    return render_template('compare_qbs.html', passers_by_year=passers_by_year, has_fig=False)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == "__main__":
    app.run(host='localhost', port='5678', debug=True)