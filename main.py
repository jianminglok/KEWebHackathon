import pyrebase
from flask import Flask, flash, redirect, render_template, request, session, abort, url_for
from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables from .env.

app = Flask(__name__)       #Initialze flask constructor

#replace with your own API key
config = {
  "apiKey": os.getenv("apiKey"), 
  "authDomain": os.getenv("authDomain"),
  "databaseURL": os.getenv("databaseURL"),
  "storageBucket": os.getenv("storageBucket"),
  "secretKey": os.getenv("secretKey")
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()
app.secret_key = config["secretKey"];

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
            
        session['email'] = email;
            
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

            session['email'] = email;
            
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
   
if __name__ == "__main__":
    app.run()