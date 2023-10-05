# ========================
# Imported External Modules
# ========================

from flask import Flask, jsonify, render_template, request, redirect, url_for, session, abort
from pymongo import MongoClient  # MongoDB Driver
from datetime import timedelta  # For session timeout
import uuid  # For generating OAuth2.0 code
import os
from functools import wraps  # For custom decorator
import pyotp
import qrcode
from io import BytesIO
import base64

business = "Battle Mountain Support"


# ======================
# File Configuration
# ======================

buffered = BytesIO()

# ======================
# App Configuration
# ======================

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(minutes=30)  # 30-minute session timeout
app.secret_key = 'your_secret_key_here'  # Secret key for Flask session

# ======================
# Environment Setup
# ======================

# Read environment variable to decide MongoDB port
is_dev = os.environ.get('IS_DEV', 'False').lower() == 'true'

# Connect to the appropriate MongoDB container
if is_dev:
    client = MongoClient('dev_db_container', 27017)
else:
    client = MongoClient('live_db_container', 27017)

# MongoDB Setup
db = client['BattleMountainIT']
collections = ['companies', 'locations', 'requests', 'quotes']

# Create collections if they don't exist
for collection in collections:
    if collection not in db.list_collection_names():
        db.create_collection(collection)

# ======================
# Hardcoded OTPs
# ======================

OTP1 = '1234'
OTP2 = '5678'

# ======================
# Middleware: Login & More
# ======================

# Custom decorator to require OTP authentication
def require_otp(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Custom decorator to require OTP authentication for a support request
def require_company_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('company_login'):
            return redirect(url_for('company_login'))
        return f(*args, **kwargs)
    return decorated_function

# ======================
# Routes
# ======================

# Auth: Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Handle POST request
    if request.method == 'POST':
        otp1 = request.form.get('otp1')
        otp2 = request.form.get('otp2')
        
        # Validate OTPs
        if otp1 == OTP1 and otp2 == OTP2:
            session['logged_in'] = True  # Set session variable
            next_url = session.pop('next_url', url_for('companies'))  # Redirect destination
            return redirect(next_url)
        else:
            return "Invalid OTPs. Please try again."
    
    # Handle GET request and render login page
    return render_template('login.html')

# Auth: Login Route
@app.route('/company_login', methods=['GET', 'POST'])
def company_login():
    # Handle POST request
    if request.method == 'POST':
        login = request.form.get('login')
        auth = request.form.get('auth')
        

        get_login = "LibertyGPK";
        get_code = "";

        # Validate OTPs
        if login == OTP1 and auth == OTP2:
            session['company_login'] = True  # Set session variable
            next_url = session.pop('next_url', url_for('companies'))  # Redirect destination
            return redirect(next_url)
        else:
            return "Invalid OTPs. Please try again."
    
    # Handle GET request and render login page
    return render_template('company_login.html')

# Auth: Logout Route
@app.route('/logout')
def logout():
    # Clear session and redirect to login
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Create new company
@app.route('/new/company', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        # Extract form data
        login = request.form['login_name']
        name = request.form['company_name']
        cid = str(uuid.uuid4())
        
        # Generate OAuth2.0 auth code
        auth = pyotp.random_base32()

        # Insert new company into database
        db['companies'].insert_one({
            'cid': cid,
            'login': login,
            'name': name,
            'auth': auth,
            'locations': [],
        })
        return redirect(url_for('companies'))
    return render_template('add_company.html')

# Create new location for a company
@app.route('/<string:cid>/new/location', methods=['GET', 'POST'])
def add_location(cid):
    # Handle POST request
    if request.method == 'POST':
        # Extract form data for location and contact info
        name = request.form['name']
        city = request.form['city']
        zip_code = request.form['zip']
        address = request.form['address']
        phone = request.form['phone']
        
        # Generate unique IDs
        lid = str(uuid.uuid4())
        login = request.form['login']

        # Generate OAuth2.0 auth code
        auth = pyotp.random_base32()

        # Create location dictionary
        new_location = {
            'lid': lid,
            'cid': cid,  # Assuming cid is defined somewhere in your code
            'name': name,  # Assuming name is defined somewhere in your code
            'city': city,  # Assuming city is defined somewhere in your code
            'zip': zip_code,  # Assuming zip_code is defined somewhere in your code
            'address': address,  # Assuming address is defined somewhere in your code
            'phone': phone,  # Assuming phone is defined somewhere in your code
            'login': login,
            'auth': auth  # This will store the TOTP secret in your database
        }
        
        # Insert into locations collection and update companies collection
        db['locations'].insert_one(new_location)
        db['companies'].update_one({'cid': cid}, {'$push': {'locations': {'lid': lid}}})
        
        return redirect(url_for('location_info', cid=cid, lid=lid))

    # Fetch the company using the provided CID
    company_name = db['companies'].find_one({'cid': cid})['name']

    # Error handling for company not found
    if company_name is None:
        return "Company not found", 404 

    return render_template('add_location.html', cid=cid, company_name=company_name)

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Remove a request based on its RID (Request ID)
@app.route('/remove/request/<string:rid>', methods=['POST'])
def remove_request(rid):
    # Search the 'requests' collection for a record with the specified RID
    request_info = db['requests'].find_one({'rid': rid})

    # Return a 404 error if no record was found
    if request_info is None:
        return "Request not found", 404

    # Extract Company ID and Location ID from the found record
    cid = request_info['cid']
    lid = request_info['lid']

    # Delete the request from the 'requests' collection
    db['requests'].delete_one({'rid': rid})
    # Update the 'locations' collection to remove the request
    db['locations'].update_many({}, {'$pull': {'requests': {'rid': rid}}})

    # Redirect to the location info page
    return redirect(url_for('location_info', cid=cid, lid=lid))

# Remove a location based on its LID (Location ID)
@app.route('/remove/location/<string:lid>', methods=['POST'])
def remove_location(lid):
    # Step 1: Delete the location itself
    location = db['locations'].find_one({'lid': lid})
    db['locations'].delete_one({'lid': lid})

    # Optional: Remove location from companies collection
    db['companies'].update_many({}, {'$pull': {'locations': {'lid': lid}}})

    return redirect(url_for('company_info', cid=location['cid']))

# Remove a company based on its CID (Company ID)
@app.route('/remove/companies/<string:cid>', methods=['POST'])
def remove_company(cid):
    # Step 1: Delete the company itself
    db['companies'].delete_one({'cid': cid})

    # Step 2: Delete all locations associated with that company
    db['locations'].delete_many({'cid': cid})

    # Step 3: Delete all requests associated with that company
    db['requests'].delete_many({'cid': cid})

    return redirect(url_for('companies'))
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
# Route to display information about a specific company
@app.route('/companies/<string:cid>/', methods=['GET'])
def company_info(cid):
    # Query the database to find the company by ID
    company = db['companies'].find_one({'cid': cid})
    if company is None:
        return "Company not found", 404

    # Find all locations associated with the company
    locations = db['locations'].find({'cid': cid})

    # Render company information along with associated locations
    return render_template('company_info.html', company=company, locations=locations)

# Route to display all locations of a specific company
@app.route('/<string:cid>/locations')
def company_locations(cid):
    # Query the database to find the company by ID
    company = db['companies'].find_one({'cid': cid})
    if not company:
        return "Company not found", 404

    # List all locations associated with this company
    locations = list(db['locations'].find({'cid': cid}))

    # Render template displaying the locations
    return render_template('company_locations.html', company=company, locations=locations)

# Route to display information about a specific location of a company
@app.route('/<string:cid>/<string:lid>/', methods=['GET'])
def location_info(cid, lid):
    # Query the database to find the location by company ID and location ID
    location = db['locations'].find_one({'cid': cid, 'lid': lid})

    # Also find the company name for displaying
    company_name = db['companies'].find_one({'cid': cid})['name']
    
    if location is None:
        return "Location not found", 404

    # Find all requests associated with this location
    requests = list(db['requests'].find({'lid': lid, 'cid': cid}))

    # Render the location information template
    return render_template('location_info.html', location=location, company_name=company_name, requests=requests)

# Your database query function to get 'auth' by 'cid' and 'lid'
def get_auth_by_cid_and_lid(cid, lid):
    # Query the database to find the location by company ID and location ID
    return db['locations'].find_one({'cid': cid, 'lid': lid}).get('auth')
    
@app.route('/<string:cid>/<string:lid>/qr', methods=['GET'])
@require_otp
def show_qr(cid, lid):
    # Retrieve TOTP secret
    location = db['locations'].find_one({'cid': cid, 'lid': lid})
    auth = location.get('auth')
    login = location.get('login')

    if not auth:
        return "Invalid cid or lid", 400

    # Generate a label and issuer for better identification
    label = login
    issuer = business

    # Generate the URL for the QR code
    totp = pyotp.TOTP(auth)
    uri = totp.provisioning_uri(name=label, issuer_name=issuer)

    # Generate the QR code
    qr = qrcode.make(uri)
    print()
    print()
    print(qr)
    print()
    print()

    buf = BytesIO()
    qr.save(buf, format="PNG")
    
    img_str = base64.b64encode(buf.getvalue()).decode()
    # Show QR Auth20 to user and ask them to verify
    return render_template('show_qr.html', qr_image=img_str, auth=auth)


@app.route('/<string:cid>/<string:lid>/support', methods=['GET', 'POST'])
def location_support(cid, lid):
    # Handle POST request to create a new support request
    if request.method == 'POST':
        #try:
        # First, check if the location ID belongs to the company ID
        location_record = db['locations'].find_one({'lid': lid, 'cid': cid})
        
        if not location_record:
            abort(404, description="Invalid location ID for this company.")
        # Collect form data
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        description = request.form['description']
        type = request.form['type']
        priority = request.form['priority']
        auth = request.form['auth']  # Collect the OTP
        print("auth")
        # Convert the OTP secret to a 6-digit code
        totp = pyotp.TOTP(location_record.get('auth'))
        six_digit_otp = totp.now()

        # Debug: Print the six_digit_otp and location_record.get('auth')
        print(f"Debug: six_digit_otp = {six_digit_otp}")
        print(f"Debug: location_record.get('auth') = {location_record.get('auth')}")

        if location_record and auth == six_digit_otp:
            # Generate a unique request ID
            rid = str(uuid.uuid4())
        else:
            return "Invalid OTP, please try again.", 400  # Invalid OTP
        
        # Create the new request object
        new_request = {
            'rid': rid,
            'cid': cid,
            'lid': lid,
            'first_name': first_name,
            'last_name': last_name,
            'description': description,
            'type': type,
            'priority': priority
        }
        
        # Insert new support request into the database
        db['requests'].insert_one(new_request)
        
        # Redirect to the new request view
        return redirect(url_for('view_request', cid=cid, lid=lid, rid=rid))
    
        #except Exception as e:
        print(f"An error occurred: {e}")

    else:  # GET request
        location_record = db['locations'].find_one({'lid': lid, 'cid': cid})
        if not location_record:
            abort(404, description="Invalid location ID for this company.")
        return render_template('location_support.html', cid=cid, lid=lid)


# Route to view details of a specific support request
@app.route('/<string:cid>/<string:lid>/<string:rid>', methods=['GET'])
def view_request(cid, lid, rid):
    # Query for the support request, location, and company info
    support_request = db['requests'].find_one({'rid': rid})
    location = db['locations'].find_one({'lid': lid})
    company = db['companies'].find_one({'cid': cid})

    # Validate that all entities exist
    if support_request and location and company:
        # Render the detailed view of the support request
        return render_template('view_request.html', support_request=support_request, location=location, company=company)
    else:
        return "Request or Location or Company not found", 404

# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

# Route for the home page
@app.route('/')
def index():
    # Log a test message
    print("YPO")
    
    # Information about the available routes and collections
    routes_info = {
        "routes": [
            {"<collection_name>": "Shows all the items in a collection in JSON format"}
        ],
        "available_collections": ["companies", "locations", "requests", "quotes"]
    }

    # Render the home page template and pass the routes_info dictionary
    return render_template('index.html', routes_info=routes_info)


@app.route('/<string:collection_name>')
@require_otp  # Apply OTP requirement
def show_collection(collection_name):
    # Check if the collection exists in the database
    if collection_name not in db.list_collection_names():
        return jsonify({"error": "Collection not found"}), 404
    
    # Fetch all items from the collection
    collection = db[collection_name]
    items = list(collection.find({}))
    
    # Convert MongoDB ObjectId to string and remove sensitive fields
    for item in items:
        item['_id'] = str(item['_id'])  # Convert to string if you want to keep it, else comment this line
        # Remove sensitive fields
        sensitive_keys = ['auth', '_id']
        for key in sensitive_keys:
            try:
                item.pop(key)
            except KeyError:
                continue  # Key does not exist, continue to next key
        
        
    # Render items in HTML template
    return render_template('show_collection.html', collection_name=collection_name, items=items)

# Route to display all companies
@app.route('/companies')
@require_otp  # Apply OTP requirement
def companies():
    # Fetch all companies from the 'companies' collection
    all_companies = list(db['companies'].find({}))
    
    # Log the companies for debugging
    print(all_companies)
    
    # Render the 'companies.html' template and pass the companies and business (business not defined in provided code)
    return render_template('companies.html', companies=all_companies, business=business)

# ======================
# Run the app
# ======================

if __name__ == '__main__':
    app.run( host="0.0.0.0", debug=True, port="5000" )
