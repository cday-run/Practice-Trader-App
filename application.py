import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #Get user's current total cash
    user = db.execute("SELECT cash FROM users WHERE id = :user_id",
        user_id=session["user_id"])
    cash = user[0]["cash"]
    #Select the stocks associated with current user
    stocks = db.execute("SELECT symbol, SUM(shares) as shares FROM transactions WHERE user_id=:user_id GROUP BY symbol",
        user_id=session["user_id"])
    #Create a dictionary for user's current portfolio
    values = {}
    #Populate the dictionary
    for i in stocks:
        values[i["symbol"]] = lookup(i["symbol"])
    #Sum holdings value
    holdings = db.execute("SELECT symbol, share_price, SUM(shares) as shares FROM transactions WHERE user_id=:user_id GROUP BY symbol",
        user_id=session["user_id"])
    amount = 0
    for i in holdings:
        i["price"] = lookup(i["symbol"])["price"]
        i["total"] = i["price"] * int(i["shares"])
        amount += i["total"]
    total = cash + amount
    return render_template("index.html", total=total, stocks=stocks, values=values, cash=cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        #Confirm stock exists
        if not lookup(request.form.get("symbol")):
            flash("Stock symbol was invalid")
            return render_template("buy.html")
        #Confirm positive number of shares ordered
        shares = int(request.form.get("shares"))
        if shares <= 0:
            flash("Must buy at least 1 share")
            return render_template("buy.html")
        #Look up current stock price
        stock = lookup(request.form.get("symbol"))
        share_price = stock["price"]
        #Get user's current funds balance
        row = db.execute("SELECT cash FROM users WHERE id = :user_id",
                          user_id=session["user_id"])
        cash = row[0]["cash"]
        #Check order cost does not exceend balance
        total_cost = share_price * shares
        if total_cost > cash:
            flash("Insufficient Funds")
            return render_template("buy.html")
        #Update user's total cash
        db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=total_cost, user_id=session["user_id"])
        #Update user's transactions
        db.execute("INSERT INTO transactions (user_id, symbol, shares, share_price, buy_sell) VALUES (:user_id, :symbol, :shares, :price, :bought)",
        user_id=session["user_id"], symbol=stock["symbol"], shares=shares, price=share_price, bought="BOUGHT")
        #Let user know purchase was successful
        flash("Purchase Successful!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT symbol, shares, share_price, buy_sell, date FROM transactions WHERE user_id=:user_id", user_id=session["user_id"])
    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide a username")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username and/or password! Have you Registered?")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

#give users ability to change password
@app.route("/change", methods=["GET","POST"])
def change():
    if request.method == "GET":
        return render_template("change.html")
    else:
        #Confirm existing username is entered
        rows = db.execute("SELECT username FROM users WHERE username=:user_id", user_id = request.form.get("username"))
        if len(rows) != 1:
            flash("Username does not exist!")
            return render_template("change.html")
        #Confirm valid password entered
        if not request.form.get("password").isalnum():
            flash("Please enter a password with only numbers and letters")
            return render_template("change.html")
        #Confirm passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords did not match!")
            return render_template("change.html")
        #Update user's password in the database
        username=request.form.get("username")
        db.execute("UPDATE users SET hash=:hash WHERE username=:user_id", hash=generate_password_hash(request.form.get("password")), user_id=username)
        flash("Password updated!")
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        #Confirm field is not blank
        if not request.form.get("symbol"):
            flash("Please enter a stock to look up")
            return render_template("quote.html")
        #Look up the stock and return apology if not found
        stock = lookup(request.form.get("symbol"))
        if stock == None:
            flash("Invalid stock symbol")
            return render_template("quote.html")
        return render_template("quoted.html", stock=stock)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        #Confirm valid username entered
        if not request.form.get("username").isalnum():
            flash("Please enter a username with only numbers and letters")
            return render_template("register.html")
        #Confirm valid password entered
        elif not request.form.get("password").isalnum():
            flash("Please enter a password with only numbers and letters")
            return render_template("register.html")
        #Confirm passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords did not match!")
            return render_template("register.html")
        #Hash the password
        password = generate_password_hash(request.form.get("password"))
        #Get username
        username = request.form.get("username")
        #Add new user to database, checking if username already taken or not
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=password)
        except:
            flash("Username is already taken!")
            return render_template("register.html")
        flash("Registration Successful!")
        return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    else:
        #Confirm stock entered is owned
        check = db.execute("SELECT symbol FROM transactions WHERE user_id=:user_id AND symbol=:symbol", user_id=session["user_id"], symbol=request.form.get("symbol"))
        if not check:
            flash("Do not own stock")
            return render_template("sell.html")
        #Confirm number of shares entered is positve int
        shares = int(request.form.get("shares"))
        if shares <= 0:
            flash("Must sell at least 1 share")
            return render_template("sell.html")
        #Get number of owned shares
        owned = db.execute("SELECT SUM(shares) as shares FROM transactions WHERE user_id=:user_id AND symbol=:symbol GROUP BY symbol",
            user_id=session["user_id"],
            symbol=request.form.get("symbol"))
        #Check number of shares sold does not exceed owned
        if owned[0]["shares"] <=0 or owned[0]["shares"] < shares:
            flash("Cannot sell more shares than owned")
            return render_template("sell.html")
        #Get current cash
        row = db.execute("SELECT cash FROM users WHERE id=:user_id",
            user_id=session["user_id"])
        cash = row[0]["cash"]
        #Lookup stock
        stock = lookup(request.form.get("symbol"))
        share_price = stock["price"]
        #Update number of shares owned
        db.execute("INSERT INTO transactions (user_id, symbol, shares, share_price, buy_sell) VALUES (:user_id, :symbol, :shares, :price, :sold)",
            user_id=session["user_id"],
            symbol=stock["symbol"],
            shares=-shares,
            price=share_price,
            sold="SOLD")
        #Update user's total cash
        db.execute("UPDATE users SET cash = cash + :price WHERE id = :user_id", price=share_price * shares, user_id=session["user_id"])
        #Indicate sale successful
        flash("Sale Successful")
        return redirect("/")

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Add cash to balance"""
    if request.method == "GET":
        return render_template("deposit.html")
    else:
        #Get value of deposit
        try:
            deposit = int(request.form.get("deposit"))
        except ValueError:
            flash("Invalid Entry!")
            return render_template("deposit.html")
        #Update user's total cash
        db.execute("UPDATE users SET cash = cash + :deposit WHERE id = :user_id", user_id=session["user_id"], deposit=deposit)
        flash("Deposit Successful!")
        #Update transaction history
        db.execute("INSERT INTO transactions (user_id, buy_sell) VALUES (:user_id, :deposit)",
            user_id=session["user_id"],
            deposit="DEPOSIT")
        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
