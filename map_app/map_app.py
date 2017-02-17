import argparse
import collections
import operator
import psycopg2.extras
from flask import Flask, request, render_template, jsonify
import time, datetime
from chart_app.chart_app import color_charge_state_calc

app = Flask(__name__)

@app.route('/', methods=['GET','POST'])
def index():
    return render_template('index.html')

@app.route('/form')
def filter_date():
    # Get data range from user
    date_range = request.args.get('daterange',0, type=str).split(" - ")
    # mktime returns UTC assuming we entered local time
    epoch_start = time.mktime(datetime.datetime.strptime(date_range[0],"%Y-%m-%d %H:%M:%S").timetuple()) #+ 25200
    epoch_end = time.mktime(datetime.datetime.strptime(date_range[1],"%Y-%m-%d %H:%M:%S").timetuple()) #+ 25200
    # So when we query the database, epoc_start_end will already be +7 in UTC

    query = "SELECT ceiling(extract(epoch from timestamp)-25200 )::int as timestamp_pdt, timestamp - interval '7 hour' as date_time_pdt, * FROM vehicle_data where EXTRACT(epoch from timestamp)>='%s' AND EXTRACT(epoch from timestamp)<'%s' " %(epoch_start, epoch_end)
    print query

    # Connect to database and query
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(query)

    # Create geojson datapoints
    vehicles, line_geojson = create_geojson(cursor)

    # pprint.pprint(point_geojson)
    # pprint.pprint(line_geojson)
    return jsonify(vehicles=vehicles, line_geojson=line_geojson)

def create_geojson(cursor):
    '''Function to thats a database cursor object and returns geojson objects which is the format necessary for MapBox to use to produce maps'''
    vehicles = collections.defaultdict(lambda: {
        'point_geojson': {'type': 'FeatureCollection', 'features': []},
        'line_string': [],
        'timestamp_list': [],
        'date_time': [],
    })

    for q in cursor:
        car_id = q['vehicle'] # need to know which are we are working with
        single_point = [q['drive_state']['longitude'],q['drive_state']['latitude']]
        data = vehicles[str(car_id)]
        data['point_geojson']['features'].append(create_point_feature(q, single_point))
        data['line_string'].append(single_point)
        data['timestamp_list'].append(int(q['timestamp_pdt']))
        data['date_time'].append(str(q['date_time_pdt']))

    # Only if the route for a given car has points, we will append the feature
    line_geojson = {
        'type': 'FeatureCollection',
        'features': [create_line_feature(car_id, data['line_string']) for car_id, data in vehicles.items() if data['line_string']],
    }
    for data in vehicles.values():
        data['timestamp_list'] = [0] + list(map(operator.sub, data['timestamp_list'][1:], data['timestamp_list'][:-1]))
    return vehicles, line_geojson

def create_point_feature(q, single_point):
    '''Helper function which is called by create_geojson to create point geojson'''

    # Create Speed Variable
    if q['drive_state']['speed']: # if it is not None
        speed = q['drive_state']['speed']
    else:
        speed = None
    # Create State Variable
    if q['charge_state']['fast_charger_present'] == True and color_charge_state_calc(q['charge_state']['charging_state'])=='yellow':
        vehicle_state_color = 'plugged_notfull' #"#0000ff"
    elif q['charge_state']['fast_charger_present'] == True and color_charge_state_calc(q['charge_state']['charging_state'])=='green':
        vehicle_state_color = 'plugged_full' #"#00cc00"
    elif q['charge_state']['fast_charger_present'] == False and color_charge_state_calc(q['charge_state']['charging_state'])=='green':
        vehicle_state_color = 'notplugged_full' #"#00cc00"
    elif q['charge_state']['fast_charger_present'] == False and q['drive_state']['speed'] is None:
        vehicle_state_color = 'notplugged_sitting' #"#ff0000"
    elif q['charge_state']['fast_charger_present'] == False and color_charge_state_calc(q['charge_state']['charging_state'])=='red':
        vehicle_state_color = 'notplugged_inuse' #"#ffff00"
    else:
        vehicle_state_color = 'other' #"#000000"

    return {
        "type": "Feature",
        "properties":
            {
                "descriptions": "<strong>SOC</strong><span> :   "+str(q['charge_state']['battery_level'])+"</span><br/> <strong>Range</strong><span> : " +str(q['charge_state']['battery_range'])+
                "</span><br/><strong>Speed</strong><span> : " + str(speed)+"</span><br/>",

                "vehicle_id": str(q['vehicle']),
                "vehicle_state": vehicle_state_color
        },
        "geometry":{"type":"Point", "coordinates": single_point }
    }

def create_line_feature(car_id, line_string):
    '''Helper function which is called by create_geojson to create line geojson'''

    return {
        "type": "Feature",
        "properties": {"vehicle_id": str(car_id)},
        "geometry":{"type":"LineString", "coordinates": line_string}
    }


parser = argparse.ArgumentParser(description='Chart app.')
parser.add_argument('--db', default='postgresql://<user>:<pass>@tesla-vehicle-api-db.ct6ob3lecz50.us-west-2.rds.amazonaws.com/tesloop', help='db connection uri [%(default)s]')

if __name__ == '__main__':
    args = parser.parse_args()
    conn = psycopg2.connect(args.db)
    app.run(host='0.0.0.0', port=8000, debug=True)
