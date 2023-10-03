from flask import Flask, jsonify, render_template, request, redirect, url_for
from pymongo import MongoClient
import uuid  # for generating OAuth2.0 code

app = Flask(__name__)

business = "Battle Mountain I.T."
try:
    client = MongoClient('localhost', 27017)  # When on a local machine
    print("Connected to MongoDB at localhost.")
except Exception as e_local:
    print("An error occurred while connecting locally:", e_local)
    
    try:
        client = MongoClient('db', 27017)  # When on a Docker instance
        print("Connected to MongoDB at Docker instance.")
    except Exception as e_docker:
        print("An error occurred while connecting in Docker:", e_docker)
        exit(1)  # Exiting because couldn't connect either way

# MongoDB setup
db = client['BattleMountainIT']

collections = ['companies', 'locations', 'users', 'requests', 'quotes']

for collection in collections:
    if collection not in db.list_collection_names():
        db.create_collection(collection)

##############################################
@app.route('/new/company', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        login = request.form['login_name']
        name = request.form['company_name']
        cid = str(uuid.uuid4())
        
        auth_code = str(uuid.uuid4())  # Generate unique OAuth2.0 code

        db['companies'].insert_one({
            'cid':cid,
            'login': login,
            'name': name,
            'auth': auth_code,
            'locations': [],
            'users': []
        })

        return redirect(url_for('companies'))

    return render_template('add_company.html')

@app.route('/<string:cid>/new/location', methods=['GET', 'POST'])
def add_location(cid):
    if request.method == 'POST':
        name = request.form['name']
        # Location info
        city = request.form['city']
        zip_code = request.form['zip']
        address = request.form['address']
        # Contact info
        phone = request.form['phone']


        lid = str(uuid.uuid4())
        login = request.form['login']
        auth = str(uuid.uuid4())
        
        new_location = {
            'lid': lid,
            'cid': cid,
            'name': name,
            'city': city,
            'zip': zip_code,
            'address': address,
            'phone':phone,
            'login': login,
            'auth': auth,
            'users': []
        }
        
        db['locations'].insert_one(new_location)
        db['companies'].update_one({'cid': cid}, {'$push': {'locations': {'lid':lid}}})
        
        return redirect(url_for('location_info', cid=cid, lid=lid))
    
    # Fetch the company using the provided cid
    company_name = db['companies'].find_one({'cid': cid})['name']
    # If the company is not found, handle it appropriately. E.g., show an error page.
    if company_name is None:
        return "Company not found", 404 
    
    return render_template('add_location.html', cid=cid, company_name=company_name)

@app.route('/<string:cid>/new/user', methods=['GET', 'POST'])
def add_user(cid):
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        role = request.form['role']
        phone = request.form['phone']
        email = request.form['email']
        lid = request.form['lid']
        uid = str(uuid.uuid4())
        auth = str(uuid.uuid4())
        
        new_user = {
            'uid': uid,
            'cid':cid,
            'lid':lid,
            'first_name': first_name,
            'last_name': last_name,
            'role': role,
            'auth': auth,
            'phone':phone,
            'email':email,
            'requests': []
        }
        
        db['users'].insert_one(new_user)
        db['companies'].update_one({'cid': cid}, {'$push': {'users': {'uid':uid}}})
        db['locations'].update_one({'lid': lid}, {'$push': {'users': {'uid':uid}}})
        
        return redirect(url_for('user_info', cid=cid, lid=lid, uid=uid))

    company_name = db['companies'].find_one({'cid': cid})['name']
    locations = db['companies'].find_one({'cid': cid})['locations']
    # Fetch the lids and get their names
    lids = locations
    print(lids)
    location_names = []
    for lid in lids:
        location = db['locations'].find_one({'lid': lid['lid']})
        print(location)
        if location:
            location_names.append({'name':location['name'],'city':location['city'],'lid':location['lid']})

    return render_template('add_user.html', cid=cid, company_name=company_name, locations=location_names )
##############################################

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
@app.route('/remove/request/<string:rid>', methods=['POST'])
def remove_request(rid):
    # Find the user ID associated with this request
    request_info = db['requests'].find_one({'rid': rid})
    if request_info is None:
        return "Request not found", 404
    
    uid = request_info['uid']
    cid = request_info['cid']
    lid = request_info['lid']

    # Delete the request and update the user and location info
    db['requests'].delete_one({'rid': rid})
    db['users'].update_many({}, {'$pull': {'requests': {'rid': rid}}})
    db['locations'].update_many({}, {'$pull': {'requests': {'rid': rid}}})

    # Redirect to the user info page
    return redirect(url_for('user_info', cid=cid, lid=lid, uid=uid))

@app.route('/remove/user/<string:uid>', methods=['POST'])
def remove_user(uid):
    # Find the user and company ID
    user_info = db['users'].find_one({'uid': uid})
    if user_info is None:
        return "User not found", 404

    cid = user_info['cid']
    rids = [req['rid'] for req in user_info.get('requests', [])]

    # Remove all associated requests from the 'requests' collection
    db['requests'].delete_many({'rid': {'$in': rids}})

   # Remove the user itself
    db['users'].delete_one({'uid': uid})

    # Remove this user from 'locations'
    db['locations'].update_many({}, {'$pull': {'users': {'uid': uid}}})

    # Redirect to the company locations page
    return redirect(url_for('location_info', cid=cid, lid=user_info.get('lid')))

@app.route('/remove/location/<string:lid>', methods=['POST'])
def remove_location(lid):
    # Step 1: Delete the location itself
    location = db['locations'].find_one({'lid': lid})
    db['locations'].delete_one({'lid': lid})

    # Step 2: Find all users at that location
    users_at_location = db['users'].find({'lid': lid})

    # Step 3: For each user found, delete their requests
    for user in users_at_location:
        uid = user['uid']
        db['requests'].delete_many({'uid': uid})

    # Step 4: Delete all users at that location
    db['users'].delete_many({'lid': lid})

    # Optional: Remove location from companies collection
    db['companies'].update_many({}, {'$pull': {'locations': {'lid': lid}}})

    return redirect(url_for('company_info', cid=location['cid']))

@app.route('/remove/companies/<string:cid>', methods=['POST'])
def remove_company(cid):
    # Step 1: Delete the company itself
    db['companies'].delete_one({'cid': cid})

    # Step 2: Delete all locations associated with that company
    db['locations'].delete_many({'cid': cid})

    # Step 3: Delete all users associated with that company
    db['users'].delete_many({'cid': cid})

    # Step 4: Delete all requests associated with that company
    db['requests'].delete_many({'cid': cid})

    return redirect(url_for('companies'))
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
@app.route('/<string:cid>/', methods=['GET'])
def company_info(cid):
    company = db['companies'].find_one({'cid': cid})
    if company is None:
        return "Company not found", 404

    locations_cursor = db['locations'].find({'cid': cid})
    locations = []
    for loc in locations_cursor:
        users_cursor = db['users'].find({'lid': loc['lid']})
        loc['users'] = list(users_cursor)
        locations.append(loc)
        
    return render_template('company_info.html', company=company, locations=locations)

@app.route('/<string:cid>/users')
def company_users(cid):
    company = db['companies'].find_one({'cid': cid})
    if not company:
        return "Company not found", 404
    users = list(db['users'].find({'cid': cid}))
    return render_template('company_users.html', company=company, users=users)

@app.route('/<string:cid>/<string:lid>/<string:uid>/', methods=['GET'])
def user_info(cid, lid, uid):
    user = db['users'].find_one({'cid': cid, 'lid': lid, 'uid': uid})
    if user is None:
        return "User not found", 404

    # Fetch the requests tied to this user by uid
    requests_cursor = db['requests'].find({'uid': uid})
    requests_list = list(requests_cursor)

    return render_template('user_info.html', user=user, requests=requests_list)

@app.route('/<string:cid>/locations')
def company_locations(cid):
    company = db['companies'].find_one({'cid': cid})
    if not company:
        return "Company not found", 404
    locations = list(db['locations'].find({'cid': cid}))
    return render_template('company_locations.html', company=company, locations=locations)

@app.route('/<string:cid>/<string:lid>/', methods=['GET'])
def location_info(cid, lid):
    location = db['locations'].find_one({'cid': cid, 'lid': lid})
    company_name = db['companies'].find_one({'cid': cid})['name']
    if location is None:
        return "Location not found", 404

    users_cursor = db['users'].find({'lid': lid})
    users = list(users_cursor)
    requests = list(db['requests'].find({'lid': lid, 'cid': cid}))

    return render_template('location_info.html', location=location, users=users, company_name=company_name, requests=requests)


@app.route('/<string:cid>/<string:lid>/users', methods=['GET'])
def location_users(cid, lid):
    # Your code for fetching users for this specific location and company
    users = db['users'].find({'cid': cid, 'lid': lid})
    location = db['locations'].find_one({'lid': lid})
    company = db['companies'].find_one({'cid': cid})
    
    # Convert to lists or other data structures as needed
    users_list = list(users)

    # If the company or location is not found, handle it appropriately. E.g., show an error page.
    if company is None or location is None:
        return "Company or Location not found", 404
    
    return render_template('location_users.html', users=users_list, company=company, location=location)

@app.route('/<string:cid>/<string:lid>/support', methods=['GET', 'POST'])
def location_support(cid, lid):
    if request.method == 'POST':
        try:
            description = request.form['description']
            uid = request.form['user']
            type = request.form['type']
            priority = request.form['priority']
            rid = str(uuid.uuid4())
            
            new_request = {
                'rid': rid,
                'cid': cid,
                'lid': lid,
                'uid': uid,
                'description': description,
                'type': type,
                'priority': priority
            }
            # Insert new support request
            db['requests'].insert_one(new_request)
            
            # Update user and location with new support request
            db['locations'].update_one({'lid': lid}, {'$push': {'requests': {'rid': rid}}})
            db['users'].update_one({'uid': uid}, {'$push': {'requests': {'rid': rid}}})
            
            return redirect(url_for('view_request', cid=cid, lid=lid, uid=uid, rid=rid))

        except Exception as e:
            print(f"An error occurred: {e}")
    
    # Fetch list of users for the given location
    location = db['locations'].find_one({'lid': lid})
    users_list = []
    if location:
        user_ids = [user['uid'] for user in location.get('users', [])]
        for uid in user_ids:
            user = db['users'].find_one({'uid': uid})
            if user:
                users_list.append({'name': f"{user['first_name']} {user['last_name']}", 'uid': uid})
    
    return render_template('location_support.html', cid=cid, lid=lid, users_list=users_list)

# view_request
@app.route('/<string:cid>/<string:lid>/<string:uid>/<string:rid>', methods=['GET'])
def view_request(cid, lid, uid, rid):
    support_request = db['requests'].find_one({'rid': rid})
    location = db['locations'].find_one({'lid': lid})
    company = db['companies'].find_one({'cid': cid})
    user = db['users'].find_one({'uid': uid})

    if support_request and location and company:
        return render_template('view_request.html', 
                                support_request=support_request, 
                                location=location, 
                                company=company,user=user)
    else:
        return "Request or Location or Company not found", 404
# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

@app.route('/')
def index():
    print("YPO")
    routes_info = {
        "routes": [
            {"<collection_name>": "Shows all the items in a collection in JSON format"}
        ],
        "available_collections": ["companies", "locations", "users", "requests", "quotes"]
    }
    return render_template('index.html', routes_info=routes_info)

@app.route('/<string:collection_name>')
def show_collection(collection_name):
    if collection_name not in db.list_collection_names():
        return jsonify({"error": "Collection not found"}), 404
    
    collection = db[collection_name]
    items = list(collection.find({}))
    
    # Convert ObjectId to string
    for item in items:
        item['_id'] = str(item['_id'])
        
    return jsonify(items)

@app.route('/companies')
def companies():
    all_companies = list(db['companies'].find({}))
    print(all_companies)
    
    return render_template('companies.html', companies=all_companies, business=business)

if __name__ == '__main__':
    app.run( host="0.0.0.0", debug=True, port="5000" )
