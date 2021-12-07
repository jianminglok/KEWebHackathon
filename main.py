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
  "storageBucket": os.getenv("storageBucket")
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

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
app.secret_key = os.getenv("secretKey") or "supersecret123"

def populate_typesense():
    print("Populating collection...")
    try:
        products = db.child("products").get()
        for p in products.each():          
            data_typesense = {"id": p.val()['sku'], "name": p.val()['name'], "price": p.val()['price'],
                "sku": p.val()['sku'], "image": p.val()['image'], "created_at": p.val()['created_at']}
            client.collections['products'].documents.create(data_typesense)
          
    except Exception as e:
        print(e)
                                                             
# Run this part during initial setup to create the typesense collection
def create_collection():
    # Drop pre-existing collection if any
    print("Creating collection..")
    try:
        client.collections['products'].delete()
    except Exception as e:
        print(e)

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
    
    populate_typesense()
    
create_collection()

#Login
@app.route("/")
def login():
    if "email" in session:
        return redirect(url_for('products'))
    else:
        return render_template("login.html")

#Sign up/ Register
@app.route("/signup")
def signup():
    return render_template("signup.html")

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
            
        return redirect(url_for('products'))
       
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
            
            #Go to main page
            return redirect(url_for('products'))
        except:
            #If there is any error, redirect to register
            return redirect(url_for('register'))

    else:
        if 'email' in session:
            return redirect(url_for('products'))
        else:
            return redirect(url_for('register'))


@app.route('/logout')
def logout():
   # remove the email from the session if it is there
   session.pop('email', None)
   return redirect(url_for('products'))

## Returns all products
@app.route('/products', methods=['GET', 'POST'])
def products():
    try:
        if request.method == 'GET':
            if 'email' in session:
                try:
                    products = db.child("products").get()
                    output = []
                    for p in products.each():
                        output.append({"id": p.key(), "name": p.val()['name'], "price": p.val()['price'], "sku": p.val()[
                                    'sku'], "image": p.val()['image'], "created_at": p.val()['created_at']})
                    return render_template("welcome.html", email=session['email'], products=output)
                except:
                    return render_template("welcome.html", email=session['email'], products={"error": "No products found"})
            else:  
                return redirect(url_for('login'))         
        else:
            ## Admin side function for us to populate the database with products
            if 'secretKey' in request.form:
                if request.form['secretKey'] == app.secret_key:  
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
                                            "sku": sku, "image": image, "created_at": created_at}
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
   
@app.route('/add', methods=['POST'])
def add_to_cart():

    _quantity = int(request.form['quantity'])
    _name = request.form['name']
   
    try:
        products = client.collections['products'].documents[_name].retrieve()
        
        '''
        products = client.collections['products'].documents.search({
            'q': _name,
            'query_by': 'name',
            'sort_by': 'created_at:desc'
        })
        '''
          
        try:
            '''
            itemArray = { _name : {'name' : p['document']['name'], 'sku' :  p['document']['sku'], 'quantity' : _quantity, 'price' : p['document']['price'], 'image' :  p['document']['image'], 'total_price': _quantity * p['document']['price']}}
            '''
            
            itemArray = { _name : {'name' : products['name'], 'sku' :  products['sku'], 'quantity' : _quantity, 'price' : products['price'], 'image' :  products['image'], 'total_price': _quantity * products['price']}}
             
            all_total_price = 0
            all_total_quantity = 0
        
            session.modified = True
            if 'cart_item' in session:
                if _name in session['cart_item']:
                    for key, value in session['cart_item'].items():
                        if _name == key:
                            old_quantity = session['cart_item'][key]['quantity']
                            total_quantity = old_quantity + _quantity
                            session['cart_item'][key]['quantity'] = total_quantity
                            session['cart_item'][key]['total_price'] = total_quantity * products['price']
                else:
                    session['cart_item'] = array_merge(session['cart_item'], itemArray)

                for key, value in session['cart_item'].items():
                    individual_quantity = int(session['cart_item'][key]['quantity'])
                    individual_price = float(session['cart_item'][key]['total_price'])
                    all_total_quantity = all_total_quantity + individual_quantity
                    all_total_price = all_total_price + individual_price
            
            else:
                session['cart_item'] = itemArray
                all_total_quantity = all_total_quantity + _quantity
                all_total_price = all_total_price + _quantity * products['price']
            
            session['all_total_quantity'] = all_total_quantity
            session['all_total_price'] = all_total_price
     
            return redirect(url_for('products'))
        except Exception as e:
            print(e)
            return redirect(url_for('products'))
    except Exception as e:
        print(e)
        return redirect(url_for('products'))

@app.route('/empty')
def empty_cart():
    try:
        email = session['email']
        session.clear()

        session['email'] = email
        return redirect(url_for('products'))
    except Exception as e:
        print(e)
        
@app.route('/delete/<string:code>')
def delete_product(code):
    try:
        all_total_price = 0
        all_total_quantity = 0
        session.modified = True
		
        for item in session['cart_item'].items():
            if item[0] == code:				
                session['cart_item'].pop(item[0], None)
                if 'cart_item' in session:
                    for key, value in session['cart_item'].items():
                        individual_quantity = int(session['cart_item'][key]['quantity'])
                        individual_price = float(session['cart_item'][key]['total_price'])
                        all_total_quantity = all_total_quantity + individual_quantity
                        all_total_price = all_total_price + individual_price
                break
		
        if all_total_quantity == 0:
            email = session['email']
            session.clear()

            session['email'] = email
        else:
            session['all_total_quantity'] = all_total_quantity
            session['all_total_price'] = all_total_price

        return redirect(url_for('products'))
    except Exception as e:
        print(e)
		
def array_merge( first_array , second_array ):
	if isinstance( first_array , list ) and isinstance( second_array , list ):
		return first_array + second_array
	elif isinstance( first_array , dict ) and isinstance( second_array , dict ):
		return dict( list( first_array.items() ) + list( second_array.items() ) )
	elif isinstance( first_array , set ) and isinstance( second_array , set ):
		return first_array.union( second_array )
	return False	
    
if __name__ == "__main__":
    app.run(debug=True)