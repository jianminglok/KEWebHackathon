import re
import pyrebase
from flask import Flask, flash, redirect, render_template, request, session, abort, url_for, Response, json
from dotenv import load_dotenv
import os
import typesense
import time

load_dotenv()  # take environment variables from .env.

app = Flask(__name__)       #Initialze flask constructor

#replace with your own API key

config = {
  "apiKey": os.getenv("firebase_apiKey"), 
  "authDomain": os.getenv("authDomain"),
  "databaseURL": os.getenv("databaseURL"),
  "storageBucket": os.getenv("storageBucket"),
  "secretKey": os.getenv("secretKey")
}

client = typesense.Client({
    "api_key": os.getenv("typesense_api_key"),
    "nodes": [{
        "host": os.getenv("typesense_host"),
        "port": '443',
        "protocol": 'https'
    }],
    'connection_timeout_seconds': 2
})


# Run this part during initial setup to create the typesense collection
"""
# Drop pre-existing collection if any
try:
    client.collections['products'].delete()
except Exception as e:
    pass

# Create a collection

create_response = client.collections.create({
    "name": "products",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "price", "type": "float"},
        {"name": "sku", "type": "string"},
        {"name": "image", "type": "string"},
        {"name": "created_at", "type": "float"}
    ],
    "default_sorting_field": "created_at"
})
"""

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
app.secret_key = config["secretKey"]

# Retrive typesense collection
client.collections['products'].retrieve()

#Login
@app.route("/")
def login():
    if "email" in session:
        return redirect(url_for('welcome'))
    else:
        return render_template("login.html")

#Sign up/ Register
@app.route("/signup")
def signup():
    return render_template("signup.html")

#Welcome page
@app.route("/welcome")
def welcome():
    if "email" in session:
        return render_template("welcome.html", email = session["email"])
    else:
        return render_template("login.html")

#If someone clicks on login, they are redirected to /result
@app.route("/result", methods = ["POST", "GET"])
def result():
    if request.method == "POST":        #Only if data has been posted
        result = request.form           #Get the data
        email = result["email"]
        password = result["pass"]
        try:
            #Try signing in the user with the given information
            user = auth.sign_in_with_email_and_password(email, password)
        except:
            #If there is any error, redirect back to login
            return redirect(url_for('login'))
            
        session['email'] = email
            
        return redirect(url_for('welcome'))
       
    else:
        return redirect(url_for('login'))
  

#If someone clicks on register, they are redirected to /register
@app.route("/register", methods = ["POST", "GET"])
def register():
    if request.method == "POST":        #Only listen to POST
        result = request.form           #Get the data submitted
        email = result["email"]
        password = result["pass"]
        try:
            #Try creating the user account using the provided data
            auth.create_user_with_email_and_password(email, password)
            #Login the user
            user = auth.sign_in_with_email_and_password(email, password)

            session['email'] = email
            
            #Go to welcome page
            return redirect(url_for('welcome'))
        except:
            #If there is any error, redirect to register
            return redirect(url_for('register'))

    else:
        if 'email' in session:
            return redirect(url_for('welcome'))
        else:
            return redirect(url_for('register'))


@app.route('/logout')
def logout():
   # remove the email from the session if it is there
   session.pop('email', None)
   return redirect(url_for('welcome'))

## Returns all products

@app.route('/products', methods=['GET', 'POST'])
def products():
    try:
        if request.method == 'GET':
            try:
                products = db.child("products").get()
                output = []
                for p in products.each():
                    output.append({"id": p.key(), "name": p.val()['name'], "price": p.val()['price'], "sku": p.val()[
                                'sku'], "image": p.val()['image'], "created_at": p.val()['created_at']})
                return Response(json.dumps({"products": output}), status=200, mimetype='application/json')
            except:
                return Response(json.dumps({"error": "No products found"}), status=400, mimetype='application/json')
        else:
            ## Admin side function for us to populate the database with products
            if 'secretKey' in request.form:
                if request.form['secretKey'] == os.getenv("secretKey"):
                    name = request.form['name']
                    price = float(request.form['price'])
                    sku = request.form['sku']
                    image = request.form['image']
                    created_at = time.time()
                    if created_at and image and sku and price and name and request.method == 'POST':
                        try:
                            data = {"name": name, "price": price,
                                    "sku": sku, "image": image, "created_at": created_at}
                            rec = db.child("products").push(data) # push data to firebase realtime database
                            data_typesense = {"id": rec['name'], "name": name, "price": price,
                                            "sku": sku, "image": image, "created_at": created_at} #creates the same record in typesense collection, but with the unique timestamp key in firebase included
                            client.collections['products'].documents.create(
                                data_typesense)
                            return Response(json.dumps({"success": True}), status=200, mimetype='application/json')
                        except Exception as e:
                            return Response(json.dumps({"error": e}), status=400, mimetype='application/json')
                else:
                    return Response(json.dumps({"error": "User not authenticated"}), status=403, mimetype='application/json')
            else:
                    return Response(json.dumps({"error": "User not authenticated"}), status=403, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"error": e}), status=400, mimetype='application/json')

# Sorts products using the keys name, price, quantity_sold

@app.route('/products/sort/<method>', methods=['GET'])
def products_sort(method):
    try:
        products = db.child("products").order_by_child(method).get()
        output = []
        for p in products.each():
            output.append({"id": p.key(), "name": p.val()['name'], "price": p.val()['price'], "sku": p.val()[
                'sku'], "image": p.val()['image'], "created_at": p.val()['created_at']})
        return Response(json.dumps({"products": output}), status=200, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"error": "No products found"}), status=400, mimetype='application/json')

# Return individual product details when product ID is passed

@app.route('/product/id/<id>', methods=['GET'])
def product(id):
    try:
        product = db.child("products").child(id).get()
        try:
            json.dumps(product.val())
            
            output = {"id": product.key(), "name": product.val()['name'], "price": product.val()['price'], "sku": product.val()[
                'sku'], "image": product.val()['image'], "created_at": product.val()['created_at']}
            return Response(json.dumps({"product": output}), status=200, mimetype='application/json')
        except Exception as e:
            return Response(json.dumps({"error": e}), status=400, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"error": "Product not found"}), status=400, mimetype='application/json')

# Search by product name using typesense

@app.route('/search/<query>', methods=['GET'])
def search(query):
    try:
        products = client.collections['products'].documents.search({
            'q': query,
            'query_by': 'name',
            'sort_by': 'created_at:desc'
        })
        try:
            output = []
            for p in products['hits']: # iterate through data returned from typesense collection
                output.append({"id": p['document']['id'], "name": p['document']['name'], "price": p['document']['price'], "sku": p['document'][
                    'sku'], "image": p['document']['image'], "created_at": p['document']['created_at']})
            return Response(json.dumps({"products": output}), status=200, mimetype='application/json')
        except:
            return Response(json.dumps({"error": "Error searching product"}), status=400, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"error": e}), status=400, mimetype='application/json')
   
if __name__ == "__main__":
    app.run()