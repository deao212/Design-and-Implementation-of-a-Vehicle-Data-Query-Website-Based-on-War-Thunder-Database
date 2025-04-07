from flask import Flask, jsonify, request
import mysql.connector
from flask_cors import CORS
import re
import logging

app = Flask(__name__)
CORS(app)

# Configuration log
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='123456',
            database='warthunder_vehicle_data',
            connect_timeout=5
        )
        logger.info("Database connection successful")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Database connection failure: {err}")
        raise

def build_where_clause(search):
    
    where_clauses = []
    params = []
    
    if search:
        try:
            # Try to parse numerical comparisons
            match = re.match(r'([<>]=?|=|!=)(\d+\.?\d*)', search)
            if match:
                operator, value = match.groups()
                where_clauses.append("max_speed %s %s")
                params.extend([operator, float(value)])
            else:
                # Text search
                where_clauses.append("(name LIKE %s OR nation LIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])
        except Exception as e:
            logger.error(f"Search parameter parsing error: {search} - {str(e)}")
    
    return where_clauses, params

def build_query(base_sql, table_name, params):
    where_clauses, where_params = build_where_clause(params.get('search'))
    sort_by = params.get('sortBy')
    sort_order = params.get('sortOrder', 'asc').upper()

    # Field mapping (handles differences between front-end field names and database field names)
    field_mapping = {
        'price': 'purchase',
        'research point': 'research',
        'crews': 'crew',
        'max speed': 'max_speed',
        'max speed at height': 'at_height',
        'flap speed limit ias': 'flap_speed_limit_ias',
        'gross weight': 'gross_weight',
        'mach number limit': 'mach_number_limit',
        'max altitude': 'max_altitude',
        'max speed limit ias': 'max_speed_limit_ias',
        'rate of climb': 'rate_of_climb',
        'take off run': 'takeoff_run',
        'turn time': 'turn_time',
        'power to weight ratio': 'power_to_weight_ratio'
    }

    # The conversion front field name is the database field name
    sort_by = field_mapping.get(sort_by, sort_by)

    # Verify that the sort field is valid
    allowed_sort = params.get('allowed_sort', [])
    if sort_by not in allowed_sort:
        sort_by = None

    order_by = ""
    if sort_by and sort_order in ['ASC', 'DESC']:
        # Add CAST processing to numeric fields
        numeric_fields = [
            'rank', 'purchase', 'research', 'AB', 'RB', 'SB', 'crew',
            'max_speed', 'at_height', 'flap_speed_limit_ias', 'gross_weight',
            'length', 'mach_number_limit', 'max_altitude', 'max_speed_limit_ias',
            'rate_of_climb', 'takeoff_run', 'turn_time', 'wingspan',
            'engine_power', 'max_speed_forward', 'max_speed_backward', 'weight',
            'power_to_weight_ratio', 'visibility', 'main_rotor_diameter'
        ]
        
        if sort_by in numeric_fields:
            order_by = f" ORDER BY CAST(`{sort_by}` AS DECIMAL) {sort_order}"
        else:
            order_by = f" ORDER BY `{sort_by}` {sort_order}"

    # Paging parameter processing
    limit = int(params.get('limit', 10))
    offset = (int(params.get('page', 1)) - 1) * limit

    query = f"{base_sql} FROM `{table_name}`"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += f"{order_by} LIMIT %s OFFSET %s"

    return query, where_params + [limit, offset]

def paginate_query(table_name, allowed_sort_fields):
    
    try:
        # Parsing parameters
        params = {
            'page': request.args.get('page', '1'),
            'limit': request.args.get('limit', '10'),
            'search': request.args.get('search', ''),
            'sortBy': request.args.get('sortBy'),
            'sortOrder': request.args.get('sortOrder', 'asc'),
            'allowed_sort': allowed_sort_fields
        }

        # Parameter verification
        try:
            page = int(params['page'])
            limit = int(params['limit'])
            if page < 1 or limit < 1 or limit > 100:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Invalid page parameter"}), 400

        # Build query
        count_sql = f"SELECT COUNT(*) AS total FROM {table_name}"
        data_sql, query_params = build_query("SELECT *", table_name, params)
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get total
        try:
            where_clauses, _ = build_where_clause(params['search'])
            count_where = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            cursor.execute(count_sql + count_where, query_params[:-2])  
            total = cursor.fetchone()['total']
        except mysql.connector.Error as err:
            logger.error(f"Data query failed: {err}")
            return jsonify({"error": "Database query failed"}), 500

        # get data
        try:
            logger.debug(f"Execute query: {data_sql} params: {query_params}")
            cursor.execute(data_sql, query_params)
            results = [convert_data_types(row) for row in cursor.fetchall()]
        except mysql.connector.Error as err:
            logger.error(f"Data query failed: {err}")
            return jsonify({"error": "Database query failed"}), 500

        cursor.close()
        conn.close()

        return jsonify({
            "items": results,
            "total": total
        })

    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        return jsonify({"error": "Server internal error"}), 500

def convert_data_types(item):
    numeric_fields = [
        'AB', 'RB', 'SB', 'at_height', 'crew', 'gross_weight',
        'length', 'max_altitude', 'max_speed', 'max_speed_limit_ias',
        'rate_of_climb', 'takeoff_run', 'turn_time', 'wingspan',
        'purchase', 'research', 'engine_power', 'weight',
        'power_to_weight_ratio', 'visibility'
    ]
    
    for field in numeric_fields:
        if field in item:
            try:
                item[field] = float(item[field]) if item[field] not in (None, '') else None
            except (ValueError, TypeError):
                item[field] = None
    
    #Handle special fields 
    item.setdefault('optics_commander_zoom', None)
    item.setdefault('optics_gunner_zoom', None)
    item.setdefault('main_rotor_diameter', None)
    
    # handle rank
    if 'rank' in item:
        rank_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,'VII': 7, 'VIII': 8}
        item['rank'] = rank_map.get(item['rank'].upper(), 0)
    
    return item

@app.route('/aviation', methods=['GET'])
def get_aviation():
    allowed = [
        'name', 'rank', 'purchase', 'research', 'AB', 'RB', 'SB', 'crew',
        'max_speed', 'at_height', 'flap_speed_limit_ias', 'gross_weight',
        'length', 'mach_number_limit', 'max_altitude', 'max_speed_limit_ias',
        'rate_of_climb', 'takeoff_run', 'turn_time', 'wingspan'
    ]
    return paginate_query('aviation', allowed)

@app.route('/ground', methods=['GET'])
def get_ground():
    allowed = [
        'name', 'rank', 'purchase', 'research', 'AB', 'RB', 'SB', 'crew',
        'engine_power', 'max_speed_forward', 'max_speed_backward', 'weight',
        'power_to_weight_ratio', 'visibility'
    ]
    return paginate_query('ground', allowed)

@app.route('/helicopters', methods=['GET'])
def get_helicopters():
    allowed = [
        'name', 'rank', 'purchase', 'research', 'AB', 'RB', 'SB',
        'at_height', 'crew', 'gross_weight', 'main_rotor_diameter',
        'max_altitude', 'max_speed', 'rate_of_climb'
    ]
    return paginate_query('helicopters', allowed)

@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Source not found"), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Server Error: {str(e)}")
    return jsonify(error="Server Error"), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)