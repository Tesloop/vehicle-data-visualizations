import argparse
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import psycopg2.extras
from flask import Flask, render_template, jsonify

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/input', methods=['GET','POST'])
def input():
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # query sql at UTC but return dates in PDT
    query = """SELECT ceiling(extract(epoch from timestamp)-25200 )::int as timestamp_pdt, timestamp AT TIME ZONE 'PDT' AS timestamp_real,drive_state, charge_state, climate_state
            FROM vehicle_data WHERE timestamp >= %s AND vehicle in (SELECT id FROM vehicle WHERE name = %s)"""
    cursor.execute(query, [datetime.utcnow() - timedelta(days=args.duration), args.vehicle])

    # Lets create some variables to store the data

    # plugged in charging, not full - BLUE/SOLID
    batt_range_plugged_incomplete = []
    # plugged in not charging, complete (sitting)- GREEN/SOLID
    batt_range_plugged_complete = []
    # unplugged, complete (sitting)- GREEN/NO-LINE
    batt_range_unplugged_complete = []
    # unplugged, in-use - YELLOW/NO-LINE
    batt_range_unplugged_inuse = []
    # unplugged, sitting - RED/NO-LINE
    batt_range_unplugged_sitting = []
    # Other
    batt_range = []

    est_batt_range = []
    bb_level = []
    speed = []
    charger_actual_current = []
    charger_pilot_current = []
    charger_power = []
    charger_voltage = []
    battery_current = [] # is driver breaking (charging) or accelerating (discharging)?
    temp = []

    station_location = []
    station_counter = 0

    # Loop through the cursor object and create above vehicle variables for each of the 5 vehicle states, as described (this is kind of a hack since HighCharts doesn't easily allow me to create 5 unique series in 1 chart)
    for i in cursor:
        # PLUGGED - CHARGING - IMCOMPLETE
        if i['charge_state']['fast_charger_present'] == True and color_charge_state_calc(i['charge_state']['charging_state'])=='yellow':
            batt_range_plugged_incomplete.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_range'], 'name':'None'})
            batt_range_plugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_inuse.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_sitting.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
        # PLUGGED - CHARGING - COMPLETE
        elif i['charge_state']['fast_charger_present'] == True and color_charge_state_calc(i['charge_state']['charging_state'])=='green':
            batt_range_plugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_range'], 'name':'None'})
            batt_range_plugged_incomplete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_inuse.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_sitting.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
        # UNPLUGGED - COMPLETE
        elif i['charge_state']['fast_charger_present'] == False and color_charge_state_calc(i['charge_state']['charging_state'])=='green':
            batt_range_unplugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_range'], 'name':'None'})
            batt_range_plugged_incomplete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_plugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_inuse.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_sitting.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
        elif i['charge_state']['fast_charger_present'] == False and i['drive_state']['speed'] is None:
            batt_range_unplugged_sitting.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_range'], 'name':'None'})
            batt_range_plugged_incomplete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_plugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_inuse.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
        elif i['charge_state']['fast_charger_present'] == False and color_charge_state_calc(i['charge_state']['charging_state'])=='red':
            batt_range_unplugged_inuse.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_range'], 'name':'None'})
            batt_range_plugged_incomplete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_plugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_complete.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
            batt_range_unplugged_sitting.append({'x': int(i['timestamp_pdt']*1000),'y': None, 'name':'None'})
        else:
            # In case I did not catch all states
            print 'SOMETHING ELSE!'

        est_batt_range.append({'x':int(i['timestamp_pdt']*1000),'y': i['charge_state']['est_battery_range'],'marker': {
                'enabled': True,
                'lineColor': color_charge_state_calc(i['charge_state']['charging_state']),
                'fillColor': color_charge_state_calc(i['charge_state']['charging_state']),
                'symbol':symbol_plug_calc(i['charge_state']['fast_charger_present'])
            }})
        bb_level.append({'x': int(i['timestamp_pdt']*1000),'y': i['charge_state']['battery_level']})

        speed.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['drive_state']['speed']})

        charger_actual_current.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['charge_state']['charger_actual_current']})
        charger_pilot_current.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['charge_state']['charger_pilot_current']})
        charger_power.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['charge_state']['charger_power']})
        charger_voltage.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['charge_state']['charger_voltage']})
        battery_current.append({'x':int(i['timestamp_pdt']*1000),'y':
        i['charge_state']['battery_current']})

        temp.append({'x':int(i['timestamp_pdt']*1000),'y':
        temp_diff_calc(i['climate_state']['outside_temp'], i['climate_state']['inside_temp'])})

        # Create Station Location (RDS Database actually has a column for this now so this is not necessary anymore)
        if i['charge_state']['fast_charger_present'] == True:
            sl = find_closest_haversine(station_locations, i['drive_state']['latitude'], i['drive_state']['longitude'])

            if station_counter == 0:
                print int(i['timestamp_pdt']*1000)
                station_location.append({'x': int(i['timestamp_pdt']*1000),'title': 'l', 'text': sl})
                station_counter = 1
                old_sl = sl
            else:
                if sl != old_sl:
                    station_location.append({'x': int(i['timestamp_pdt']*1000),'title':'l','text': sl})
                    old_sl = sl
                else: # same station, no need to update
                    continue

    return jsonify(
            batt_range_plugged_incomplete = batt_range_plugged_incomplete,
            batt_range_plugged_complete = batt_range_plugged_complete,
            batt_range_unplugged_complete = batt_range_unplugged_complete,
            batt_range_unplugged_inuse = batt_range_unplugged_inuse,
            batt_range_unplugged_sitting = batt_range_unplugged_sitting,

            est_batt_range=est_batt_range,
            bb_level=bb_level,

            speed = speed,

            charger_actual_current = charger_actual_current,
            charger_pilot_current = charger_pilot_current,
            charger_power = charger_power,
            charger_voltage = charger_voltage,
            battery_current = battery_current,

            temp = temp,

            station_location = station_location
        )

def temp_diff_calc(outtemp, intemp):
    '''Helper function to compute temperature difference'''
    if intemp is None or outtemp is None:
        return None
    else:
        return outtemp - intemp

def color_charge_state_calc(state):
    '''Helper function to return the color for a given vehicle driving state'''
    if state=='Charging' or state=='Starting': # still charging
        return 'yellow'
    elif state=='Disconnected':
        return 'red'
    else: # Complete and charger=False
        return 'green'

def symbol_plug_calc(charger):
    '''Helper function to return a shape for a given vehicle charging state'''
    if charger == True:
        return 'square'
    else:
        return 'circle'

def find_closest_haversine(station_locations, latitude1, longitude1):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    smallest_distance = 'inf'
    closest_station = None

    for i in station_locations:
        lat1 = latitude1
        lon1 = longitude1
        lat2 = station_locations[i]['lat']
        lon2 = station_locations[i]['long']

        # convert decimal degrees to radians
        # print lat1, lon1, lat2, lon2
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        distance = 2 * asin(sqrt(a)) * 6371 # Radius of earth in kilometers. Use 3956 for miles

        if distance < smallest_distance:
            smallest_distance = distance
            closest_station = i
    return closest_station


station_locations = {
    'Culver City':	{'lat':33.985441, 'long':-118.395128},
    'Redondo':	{'lat':33.893874,'long':-118.366603},
    'Fountain Valley':	{'lat':33.703083,'long':-117.934112},
    'Rancho Cucamunga':	{'lat':34.113481,'long':-117.53257},
    'Barstow':	{'lat':34.849786,'long':-117.084904},
    'Primm':	{'lat':35.610835,'long':-115.386108},
    'San Juan Capistrano':	{'lat':33.498386,'long':-117.662842},
    'Las Vegas':	{'lat':36.165938,'long':-115.139143},
    'Oxnard':	{'lat':34.24046	,'long':119.177811},
    'Buellton':	{'lat':34.615481,'long':-120.188384},
    'Santa Barbara': {'lat':34.433607,'long':-119.745386},
    'Atascadero':	{'lat':33.104215,'long':-117.266726},
    'Harris Ranch':	{'lat':36.253164,'long':-120.238534},
    'Gilroy':	{'lat':37.025384,'long':-121.564419},
    'San Mateo':	{'lat':37.546038,'long':-122.290192},
    'Mountain View':	{'lat':37.414323,'long':-122.077321},
    'Tejon Ranch':	{'lat':34.98661	,'long':118.9463},
    'Buttonwillow':	{'lat':35.400244,'long':-119.397521},
    'Temecula':	{'lat':33.524831,'long':-117.154181},
    'Cabazon':	{'lat':33.928917,'long':-116.815845},
    'Indio':	{'lat':33.742618,'long':-116.213048},
    'San Diego':	{'lat':32.902554,'long':-117.193395}
    }


parser = argparse.ArgumentParser(description='Chart app.')
parser.add_argument('--db', default='postgresql://<user>:<pass>@tesla-vehicle-api-db.ct6ob3lecz50.us-west-2.rds.amazonaws.com/tesloop', help='db connection uri [%(default)s]')
parser.add_argument('--duration', type=int, default=7, help='number of days worth of data [%(default)s]')
parser.add_argument('--vehicle', default='eHawk', help='vehicle name [%(default)s]')

if __name__ == '__main__':
    args = parser.parse_args()
    conn = psycopg2.connect(args.db)
    app.run(debug=True)
