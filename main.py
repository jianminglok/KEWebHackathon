import pyrebase
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    abort,
    url_for,
    Response,
    json,
)
from dotenv import load_dotenv
import os
import typesense
import time

load_dotenv()  # take environment variables from .env.

app = Flask(__name__)  # Initialze flask constructor

# replace with your own API key
config = {
    "apiKey": os.getenv("firebase_apiKey"),
    "authDomain": os.getenv("authDomain"),
    "databaseURL": os.getenv("databaseURL"),
    "storageBucket": os.getenv("storageBucket"),
}

client = typesense.Client(
    {
        "api_key": os.getenv("typesense_api_key"),
        "nodes": [
            {"host": os.getenv("typesense_host"), "port": "443", "protocol": "https"}
        ],
        "connection_timeout_seconds": 2,
    }
)

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
app.secret_key = os.getenv("secretKey") or "supersecret123"


def populate_typesense():
    """
    This function retrieves all the data from the Firebase database
    and populate them into Typesense for quick searching and sorting
    """
    print("Populating collection...")
    try:
        products = db.child("products").get()
        for p in products.each():
            data_typesense = {
                "id": p.key(),
                "name": p.val()["name"],
                "price": p.val()["price"],
                "sku": p.val()["sku"],
                "image": p.val()["image"],
                "created_at": p.val()["created_at"],
            }
            client.collections["products"].documents.create(data_typesense)
    except Exception as e:
        print(e)


# Run this part during initial setup to create the typesense collection
def create_collection():
    """
    This function drops any pre-existing collection from Typesense
    and creates a new collection, in case of any errors
    """
    # Drop pre-existing collection if any
    print("Creating collection..")
    try:
        client.collections["products"].delete()
    except Exception as e:
        print(e)

    # Create a collection
    create_response = client.collections.create(
        {
            "name": "products",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "price", "type": "float"},
                {"name": "sku", "type": "string"},
                {"name": "image", "type": "string"},
                {"name": "created_at", "type": "float"}
            ],
            "default_sorting_field": "created_at",
        }
    )

    populate_typesense()

create_collection()

def authenticated():
    """
    Checks if user is authenticated
    """
    if "email" in session:
        return True
    else:
        return False

# Login
@app.route("/")
def login():
    """
    Function called when user browses the "/" route
    """
    if authenticated():
        return redirect(url_for("products"))
    else:
        return render_template("login.html")


# Sign up/ Register
@app.route("/signup")
def signup():
    """
    Function called when user browses the "/signup" route
    """
    return render_template("signup.html")


# If someone clicks on login, they are redirected to /result
@app.route("/result", methods=["POST"])
def result():
    """
    Function called when user press the login button, check if
    user is signed in and redirect users to main page
    """
    if request.method == "POST":  # Only if data has been posted
        result = request.form  # Get the data
        email = result["email"]
        password = result["pass"]
        try:
            # Try signing in the user with the given information
            user = auth.sign_in_with_email_and_password(email, password)
        except:
            # If there is any error, redirect back to login
            return redirect(url_for("login"))

        session["email"] = email

        return redirect(url_for("products"))
    else:
        return redirect(url_for("login"))


# If someone clicks on register, they are redirected to /register
@app.route("/register", methods=["POST", "GET"])
def register():
    """
    Function called when user press the signup button, creates new user
    in the Firebase Authentication and sign the user into the main page
    """
    if request.method == "POST":  # Only listen to POST
        result = request.form  # Get the data submitted
        email = result["email"]
        password = result["pass"]
        try:
            # Try creating the user account using the provided data
            auth.create_user_with_email_and_password(email, password)
            # Login the user
            user = auth.sign_in_with_email_and_password(email, password)

            session["email"] = email

            # Go to main page
            return redirect(url_for("products"))
        except:
            # If there is any error, redirect to register
            return redirect(url_for("register"))

    else:
        if authenticated():
            return redirect(url_for("products"))
        else:
            return redirect(url_for("register"))


@app.route("/logout")
def logout():
    """
    Function called when user press the logout button, clear the user session
    """
    # remove the email from the session if it is there
    session.pop("email", None)
    return redirect(url_for("products"))


# Returns all products
@app.route("/products", methods=["GET"])
def products():
    """
    Function called when user access the /products page, displays all products
    retrieved from the database
    """
    try:
        if request.method == "GET":
            if authenticated():
                try:
                    products = db.child("products").get()
                    output = []
                    for p in products.each():
                        output.append(
                            {
                                "id": p.key(),
                                "name": p.val()["name"],
                                "price": p.val()["price"],
                                "sku": p.val()["sku"],
                                "image": p.val()["image"],
                                "created_at": p.val()["created_at"]
                            }
                        )
                    return render_template(
                        "welcome.html", email=session["email"], products=output
                    )
                except:
                    return render_template(
                        "welcome.html",
                        email=session["email"],
                        products={"error": "No products found"},
                    )
            else:
                return redirect(url_for("login"))
    except Exception as e:
        return Response(
            json.dumps({"error": e}), status=400, mimetype="application/json"
        )


# Return individual product details when product ID is passed
@app.route("/products/id/<id>", methods=["GET"])
def product(id):
    """
    Function called when user access the /products/id/<id> page, display particular product
    based on ID
    """
    if authenticated():
        try:
            products = client.collections["products"].documents[id].retrieve()
            try:
                return render_template(
                    "product.html", email=session["email"], product=products
                )
            except Exception as e:
                return Response(
                    json.dumps({"error": e}), status=400, mimetype="application/json"
                )
        except Exception as e:
            return Response(
                json.dumps({"error": "Product not found"}),
                status=400,
                mimetype="application/json",
            )
    else:
        return redirect(url_for("login"))


@app.route("/add", methods=["POST"])
def add_to_cart():
    """
    Function called when user presses the Add to Cart button, adds particular product
    and quantity into the cart and display in page.
    """
    if authenticated():
        _quantity = int(request.form["quantity"])
        _id = request.form["name"]

        try:
            products = client.collections["products"].documents[_id].retrieve()
            try:
                itemArray = {
                    _id: {
                        "id": _id,
                        "name": products["name"],
                        "sku": products["sku"],
                        "quantity": _quantity,
                        "price": products["price"],
                        "image": products["image"],
                        "total_price": _quantity * products["price"]
                    }
                }

                all_total_price = 0
                all_total_quantity = 0

                session.modified = True
                if "cart_item" in session:
                    if _id in session["cart_item"]:
                        for key, value in session["cart_item"].items():
                            if _id == key:
                                old_quantity = session["cart_item"][key]["quantity"]
                                total_quantity = old_quantity + _quantity
                                session["cart_item"][key]["quantity"] = total_quantity
                                session["cart_item"][key]["total_price"] = (
                                    total_quantity * products["price"]
                                )
                    else:
                        session["cart_item"] = array_merge(
                            session["cart_item"], itemArray
                        )

                    for key, value in session["cart_item"].items():
                        individual_quantity = int(session["cart_item"][key]["quantity"])
                        individual_price = float(
                            session["cart_item"][key]["total_price"]
                        )
                        all_total_quantity = all_total_quantity + individual_quantity
                        all_total_price = all_total_price + individual_price

                else:
                    session["cart_item"] = itemArray
                    all_total_quantity = all_total_quantity + _quantity
                    all_total_price = all_total_price + _quantity * products["price"]

                session["all_total_quantity"] = all_total_quantity
                session["all_total_price"] = all_total_price

                return redirect(url_for("products"))
            except Exception as e:
                return redirect(url_for("products"))
        except Exception as e:
            return redirect(url_for("products"))
    else:
        return redirect(url_for("products"))

@app.route("/empty")
def empty_cart():
    """
    Function called when user presses the Empty Cart button, removes all
    products from the cart
    """
    if authenticated():
        try:
            email = session["email"]
            session.clear()

            session["email"] = email
            return redirect(url_for("products"))
        except Exception as e:
            print(e)
    else:
        return redirect(url_for("products"))


@app.route("/delete/<string:code>")
def delete_product(code):
    """
    Function called when user presses the Delete button, removes particular
    product from the cart and update total quantity and price
    """
    if authenticated():
        try:
            all_total_price = 0
            all_total_quantity = 0
            session.modified = True

            for item in session["cart_item"].items():
                if item[0] == code:
                    session["cart_item"].pop(item[0], None)
                    if "cart_item" in session:
                        for key, value in session["cart_item"].items():
                            individual_quantity = int(
                                session["cart_item"][key]["quantity"]
                            )
                            individual_price = float(
                                session["cart_item"][key]["total_price"]
                            )
                            all_total_quantity = (
                                all_total_quantity + individual_quantity
                            )
                            all_total_price = all_total_price + individual_price
                    break

            if all_total_quantity == 0:
                email = session["email"]
                session.clear()

                session["email"] = email
            else:
                session["all_total_quantity"] = all_total_quantity
                session["all_total_price"] = all_total_price

            return redirect(url_for("products"))
        except Exception as e:
            print(e)
    else:
        return redirect(url_for("products"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    """
    Function called when user presses the Checkout button, checkout items
    from cart and empty the cart
    """
    if authenticated():
        if request.method == "GET":
            return render_template("checkout.html", email=session["email"])
        else:
            name = request.form["name"]
            address = request.form["address"]
            phone = request.form["phone"]
            created_at = time.time()

            try:
                if (
                    "cart_item"
                    and "all_total_quantity"
                    and "all_total_price" in session
                ):
                    order_data = {
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": session["email"],
                        "created_at": created_at,
                        "items": session["cart_item"],
                        "total_quantity": session["all_total_quantity"],
                        "total_price": session["all_total_price"]
                    }
                    try:
                        rec = db.child("orders").push(order_data)
                        email = session[
                            "email"
                        ]  # clear cart when order placed successfully
                        session.clear()
                        session["email"] = email
                        return render_template(
                            "order.html",
                            email=session["email"],
                            order_number=rec["name"],
                        )
                    except Exception as e:
                        print(e)
                else:
                    return redirect(url_for("products"))
            except Exception as e:
                print(e)
    else:
        return redirect(url_for("products"))

# Returns all orders
@app.route("/vieworder", methods=["GET"])
def vieworder():
    """
    Function called when user access the /products page, displays all products
    retrieved from the database
    """
    try:
        if request.method == "GET":
            if authenticated():
                try:
                    products = db.child("orders").get()
                    output = []
                    for p in products.each():
                        if p.val()['email'] == session['email']:
                            output.append(
                                {
                                    "id": p.key(),
                                    "name": p.val()["name"],
                                    "phone": p.val()["phone"],
                                    "address": p.val()["address"],
                                    "total_price": p.val()["total_price"],
                                    "total_quantity": p.val()["total_quantity"],
                                    "items": p.val()["items"],
                                    "created_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.val()["created_at"]))
                                }
                            )
                    return render_template(
                        "vieworder.html", email=session["email"], orders=output
                    )
                except:
                    return render_template(
                        "vieworder.html",
                        email=session["email"],
                        orders={"error": "No orders found"},
                    )
            else:
                return redirect(url_for("login"))
    except Exception as e:
        return Response(
            json.dumps({"error": e}), status=400, mimetype="application/json"
        )

"""
APIs for React
"""

@app.route("/api/login", methods=["POST"])
def api_login():
    if request.method == "POST":  # Only if data has been posted
        result = request.form  # Get the data
        email = result["email"]
        password = result["pass"]
        try:
            # Try signing in the user with the given information
            user = auth.sign_in_with_email_and_password(email, password)
        except:
            # If there is any error, redirect back to login
            return Response(
                json.dumps({"error": "Wrong username/password"}),
                status=400,
                mimetype="application/json",
            )
        session["email"] = email
        return Response(
            json.dumps({"success": "Successful authentication"}),
            status=200,
            mimetype="application/json",
        )
    else:
        return Response(
            json.dumps({"error": "Method not POST"}),
            status=400,
            mimetype="application/json",
        )


@app.route("/api/register", methods=["POST"])
def api_register():
    if request.method == "POST":  # Only if data has been posted
        result = request.form  # Get the data submitted
        email = result["email"]
        password = result["pass"]
        try:
            # Try creating the user account using the provided data
            auth.create_user_with_email_and_password(email, password)
            # Login the user
            user = auth.sign_in_with_email_and_password(email, password)
            session["email"] = email
            return Response(
                json.dumps({"success": "Successful registration"}),
                status=200,
                mimetype="application/json",
            )
        except:
            # If there is any error, display
            return Response(
                json.dumps({"error": "Error in registration"}),
                status=400,
                mimetype="application/json",
            )
    else:
        return Response(
            json.dumps({"error": "Method not POST"}),
            status=400,
            mimetype="application/json",
        )


@app.route("/api/logout", methods=["GET"])
def api_logout():
    if request.method == "GET":
        # remove the email from the session if it is there
        session.pop("email", None)
        return Response(
            json.dumps({"success": "Successfully logged out"}),
            status=200,
            mimetype="application/json",
        )
    else:
        return Response(
            json.dumps({"error": "Method not GET"}),
            status=400,
            mimetype="application/json",
        )


@app.route("/api/products/addproduct", methods=["POST"])
def api_addproduct():
    if authenticated():
        if "secretKey" in request.form:
            if request.form["secretKey"] == app.secret_key:
                name = request.form["name"]
                price = float(request.form["price"])
                sku = request.form["sku"]
                image = request.form["image"]
                created_at = time.time()
                if (
                    created_at
                    and image
                    and sku
                    and price
                    and name
                    and request.method == "POST"
                ):
                    try:
                        data = {
                            "name": name,
                            "price": price,
                            "sku": sku,
                            "image": image,
                            "created_at": created_at,
                        }
                        rec = db.child("products").push(
                            data
                        )  # push data to firebase realtime database
                        data_typesense = {
                            "id": rec["name"],
                            "name": name,
                            "price": price,
                            "sku": sku,
                            "image": image,
                            "created_at": created_at
                        }
                        client.collections["products"].documents.create(data_typesense)
                        return Response(
                            json.dumps({"success": True}),
                            status=200,
                            mimetype="application/json",
                        )
                    except Exception as e:
                        return Response(
                            json.dumps({"error": e}),
                            status=400,
                            mimetype="application/json",
                        )
                else:
                    return Response(
                        json.dumps({"error": "Missing data"}),
                        status=400,
                        mimetype="application/json",
                    )
            else:
                return Response(
                    json.dumps({"error": "User not authenticated"}),
                    status=403,
                    mimetype="application/json",
                )
        else:
            return Response(
                json.dumps({"error": "User not authenticated"}),
                status=403,
                mimetype="application/json",
            )
    else:
        return Response(
                json.dumps({"error": "User not authenticated"}),
                status=403,
                mimetype="application/json",
            )

@app.route("/api/products", methods=["GET"])
def api_products():
    try:
        if request.method == "GET":
            if authenticated():
                try:
                    products = db.child("products").get()
                    output = []
                    for p in products.each():
                        output.append(
                            {
                                "id": p.key(),
                                "name": p.val()["name"],
                                "price": p.val()["price"],
                                "sku": p.val()["sku"],
                                "image": p.val()["image"],
                                "created_at": p.val()["created_at"]
                            }
                        )
                    return Response(
                        json.dumps({"success": output}),
                        status=200,
                        mimetype="application/json",
                    )
                except:
                    return Response(
                        json.dumps({"error": "No products found"}),
                        status=200,
                        mimetype="application/json",
                    )
            else:
                return Response(
                    json.dumps({"error": "User not authenticated"}),
                    status=403,
                    mimetype="application/json",
                )
    except Exception as e:
        return Response(
            json.dumps({"error": e}), status=400, mimetype="application/json"
        )


@app.route("/api/products/id/<id>", methods=["GET"])
def api_product(id):
    if authenticated():
        try:
            products = client.collections["products"].documents[id].retrieve()
            try:
                return Response(
                    json.dumps({"success": products}),
                    status=200,
                    mimetype="application/json",
                )
            except Exception as e:
                return Response(
                    json.dumps({"error": e}), status=400, mimetype="application/json"
                )
        except Exception as e:
            return Response(
                json.dumps({"error": "Product not found"}),
                status=200,
                mimetype="application/json",
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


# Sorts products using the keys name, price
@app.route("/api/products/sort/<method>", methods=["GET"])
def api_products_sort(method):
    if authenticated():
        try:
            products = db.child("products").order_by_child(method).get()
            output = []
            for p in products.each():
                output.append(
                    {
                        "id": p.key(),
                        "name": p.val()["name"],
                        "price": p.val()["price"],
                        "sku": p.val()["sku"],
                        "image": p.val()["image"],
                        "created_at": p.val()["created_at"]
                    }
                )
            return Response(
                json.dumps({"success": output}), status=200, mimetype="application/json"
            )
        except Exception as e:
            print(e)
            return Response(
                json.dumps({"error": "No products found"}),
                status=200,
                mimetype="application/json",
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


# Search by product name using typesense
@app.route("/api/products/search/<query>", methods=["GET"])
def api_search(query):
    if authenticated():
        try:
            products = client.collections["products"].documents.search(
                {"q": query, "query_by": "name", "sort_by": "created_at:desc"}
            )
            try:
                output = []
                # iterate through data returned from typesense collection
                for p in products["hits"]:
                    output.append(
                        {
                            "id": p["document"]["id"],
                            "name": p["document"]["name"],
                            "price": p["document"]["price"],
                            "sku": p["document"]["sku"],
                            "image": p["document"]["image"],
                            "created_at": p["document"]["created_at"]
                        }
                    )
                return Response(
                    json.dumps({"success": output}),
                    status=200,
                    mimetype="application/json",
                )
            except:
                return Response(
                    json.dumps({"error": "Error searching product"}),
                    status=400,
                    mimetype="application/json",
                )
        except Exception as e:
            return Response(
                json.dumps({"error": e}), status=400, mimetype="application/json"
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


@app.route("/api/products/add", methods=["POST"])
def api_add_to_cart():
    if authenticated():
        _quantity = int(request.form["quantity"])
        _id = request.form["name"]

        try:
            products = client.collections["products"].documents[_id].retrieve()
            try:
                itemArray = {
                    _id: {
                        "id": _id,
                        "name": products["name"],
                        "sku": products["sku"],
                        "quantity": _quantity,
                        "price": products["price"],
                        "image": products["image"],
                        "total_price": _quantity * products["price"]
                    }
                }

                all_total_price = 0
                all_total_quantity = 0
                total_items = []

                session.modified = True
                if "cart_item" in session:
                    if _id in session["cart_item"]:
                        for key, value in session["cart_item"].items():
                            if _id == key:
                                old_quantity = session["cart_item"][key]["quantity"]
                                total_quantity = old_quantity + _quantity
                                session["cart_item"][key]["quantity"] = total_quantity
                                session["cart_item"][key]["total_price"] = (
                                    total_quantity * products["price"]
                                )
                    else:
                        session["cart_item"] = array_merge(
                            session["cart_item"], itemArray
                        )

                    for key, value in session["cart_item"].items():
                        individual_quantity = int(session["cart_item"][key]["quantity"])
                        individual_price = float(
                            session["cart_item"][key]["total_price"]
                        )
                        all_total_quantity = all_total_quantity + individual_quantity
                        all_total_price = all_total_price + individual_price

                else:
                    session["cart_item"] = itemArray
                    all_total_quantity = all_total_quantity + _quantity
                    all_total_price = all_total_price + _quantity * products["price"]

                session["all_total_quantity"] = all_total_quantity
                session["all_total_price"] = all_total_price

                for item in session["cart_item"].items():
                    total_items.append(item)

                order_data = {
                    "email": session["email"],
                    "items": total_items,
                    "all_total_quantity": all_total_quantity,
                    "all_total_price": all_total_price,
                }
                return Response(
                    json.dumps({"success": order_data}),
                    status=200,
                    mimetype="application/json",
                )
            except Exception as e:
                return Response(
                    json.dumps({"error": e}), status=400, mimetype="application/json"
                )
        except Exception as e:
            return Response(
                json.dumps({"error": e}), status=400, mimetype="application/json"
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


@app.route("/api/products/empty")
def api_empty_cart():
    if authenticated():
        try:
            email = session["email"]
            session.clear()
            session["email"] = email
            return Response(
                json.dumps({"success": "Successfully emptied cart"}),
                status=200,
                mimetype="application/json",
            )
        except Exception as e:
            return Response(
                json.dumps({"error": e}), status=400, mimetype="application/json"
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


@app.route("/api/products/delete/<string:code>")
def api_delete_product(code):
    if authenticated():
        try:
            all_total_price = 0
            all_total_quantity = 0
            session.modified = True
            total_items = []

            if "cart_item" in session:

                for item in session["cart_item"].items():
                    if item[0] == code:
                        session["cart_item"].pop(item[0], None)
                        break
                    else:
                        continue

                for item in session["cart_item"].items():
                    total_items.append(item)

                for key, value in session["cart_item"].items():
                    individual_quantity = int(session["cart_item"][key]["quantity"])
                    individual_price = float(session["cart_item"][key]["total_price"])
                    all_total_quantity = all_total_quantity + individual_quantity
                    all_total_price = all_total_price + individual_price

                if all_total_quantity == 0:
                    email = session["email"]
                    session.clear()

                    session["email"] = email
                else:
                    session["all_total_quantity"] = all_total_quantity
                    session["all_total_price"] = all_total_price

            order_data = {
                "email": session["email"],
                "items": total_items,
                "all_total_quantity": all_total_quantity,
                "all_total_price": all_total_price,
            }
            return Response(
                json.dumps({"success": order_data}),
                status=200,
                mimetype="application/json",
            )
        except Exception as e:
            return Response(
                json.dumps({"error": e}), status=400, mimetype="application/json"
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


@app.route("/api/products/cart")
def api_cart():
    if authenticated():
        try:
            all_total_price = 0
            all_total_quantity = 0
            session.modified = True

            total_items = []

            if "cart_item" in session:
                for item in session["cart_item"].items():
                    total_items.append(item)

                for key, value in session["cart_item"].items():
                    individual_quantity = int(session["cart_item"][key]["quantity"])
                    individual_price = float(session["cart_item"][key]["total_price"])
                    all_total_quantity = all_total_quantity + individual_quantity
                    all_total_price = all_total_price + individual_price

            order_data = {
                "email": session["email"],
                "items": total_items,
                "all_total_quantity": all_total_quantity,
                "all_total_price": all_total_price,
            }
            return Response(
                json.dumps({"success": order_data}),
                status=200,
                mimetype="application/json",
            )
        except Exception as e:
            return Response(
                json.dumps({"error": e}), status=400, mimetype="application/json"
            )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )


@app.route("/api/products/checkout", methods=["GET", "POST"])
def api_checkout():
    if authenticated():
        if request.method == "GET":
            return Response(
                json.dumps({"error": "Method not POST"}),
                status=400,
                mimetype="application/json",
            )
        else:
            name = request.form["name"]
            address = request.form["address"]
            phone = request.form["phone"]
            created_at = time.time()
            try:
                if (
                    "cart_item"
                    and "all_total_quantity"
                    and "all_total_price" in session
                ):
                    order_data = {
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": session["email"],
                        "created_at": created_at,
                        "items": session["cart_item"],
                        "total_quantity": session["all_total_quantity"],
                        "total_price": session["all_total_price"]
                    }
                    try:
                        rec = db.child("orders").push(order_data)
                        email = session[
                            "email"
                        ]  # clear cart when order placed successfully
                        session.clear()
                        session["email"] = email
                        return Response(
                            json.dumps({"success": rec["name"]}),
                            status=200,
                            mimetype="application/json",
                        )
                    except Exception as e:
                        return Response(
                            json.dumps({"error": e}),
                            status=400,
                            mimetype="application/json",
                        )
                else:
                    return Response(
                        json.dumps({"error": "No items in cart"}),
                        status=400,
                        mimetype="application/json",
                    )
            except Exception as e:
                return Response(
                    json.dumps({"error": e}), status=400, mimetype="application/json"
                )
    else:
        return Response(
            json.dumps({"error": "User not authenticated"}),
            status=403,
            mimetype="application/json",
        )

# Returns all products
@app.route("/api/vieworder", methods=["GET"])
def api_vieworder():
    try:
        if request.method == "GET":
            if authenticated():
                try:
                    products = db.child("orders").get()
                    output = []
                    for p in products.each():
                        if p.val()['email'] == session['email']:
                            output.append(
                                {
                                    "id": p.key(),
                                    "name": p.val()["name"],
                                    "phone": p.val()["phone"],
                                    "address": p.val()["address"],
                                    "total_price": p.val()["total_price"],
                                    "total_quantity": p.val()["total_quantity"],
                                    "items": p.val()["items"],
                                    "created_at": p.val()["created_at"]
                                }
                            )
                    return Response(
                            json.dumps({"success": output}),
                            status=200,
                            mimetype="application/json",
                        )
                except:
                    return Response(
                        json.dumps({"error": "No orders"}),
                        status=400,
                        mimetype="application/json",
                    )
            else:
                return Response(
                    json.dumps({"error": "User not authenticated"}),
                    status=403,
                    mimetype="application/json",
                )
    except Exception as e:
        return Response(
            json.dumps({"error": e}), status=400, mimetype="application/json"
        )

def array_merge(first_array, second_array):
    """
    Function used to merge two arrays together, supplementary function
    """
    if isinstance(first_array, list) and isinstance(second_array, list):
        return first_array + second_array
    elif isinstance(first_array, dict) and isinstance(second_array, dict):
        return dict(list(first_array.items()) + list(second_array.items()))
    elif isinstance(first_array, set) and isinstance(second_array, set):
        return first_array.union(second_array)
    return False


if __name__ == "__main__":
    app.run()
