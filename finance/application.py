from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    if request.method == "GET":
        user_id = session["user_id"]
        rows = (db.execute("SELECT * FROM user_stock WHERE (id=:user_id AND share>0)", user_id = user_id))
        stocks = []
        total_asset = 0
        for row in rows:
            stock = lookup(row["symbol"])
            # return error if invalid symbol
            if stock == None:
                return apology("Invalid stock symbol")
            else:
                stock_symbol = stock["symbol"]
                stock_name = stock["name"]
                stock_price = stock["price"]
                stock_share = row["share"]
                total = stock_price * stock_share
                item = (stock_symbol, stock_name, stock_share, stock_price, total)
                stocks.append(item)
                total_asset += total
        rows = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=user_id)
        cash = float(rows[0]["cash"])
        total_asset += cash
        cash_item = ('CASH', '', '', '', cash)
        stocks.append(cash_item)
        return render_template("index.html", stocks = stocks, total = total_asset)
    else:
        return apology("Invalid request method")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    # TODO: render bought.html
    error_float2int = 0.00001
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        # if invalid symbol
        if stock == None:
            return apology("Invalid symbol")
        share = float(request.form.get("share"))
        # if invalid share
        if (share <= 0) or (share - int(share) >= error_float2int):
            return apology("Invalid number of share")
        # valid symbol and share, but if insufficient cash
        user_rows = db.execute("SELECT * FROM users WHERE ID = :user_id", user_id = user_id)
        if len(user_rows)!=1:
            return apology("Multiple users exist")
        cost = stock['price'] * share
        if (cost > user_rows[0]["cash"]):
            return apology("Insufficient cash")
        
        # valid transaction
        share = int(share)
        (db.execute("INSERT INTO transaction_history (id, symbol, share, price) VALUES (:user_id,:symbol,:share,:price)",
            user_id = user_id, 
            symbol = stock['symbol'],
            share = share,
            price = stock['price'])
        )
        
        # update user_stock
        rows = db.execute("SELECT * FROM user_stock WHERE (id=:user_id AND symbol=:symbol)", user_id=user_id, symbol=stock['symbol'])
        # if no such stock purchased before
        if len(rows) == 0:
            db.execute("INSERT INTO user_stock (id, symbol, share) VALUES (:user_id, :symbol, :share)", user_id=user_id, symbol=stock['symbol'], share=share)
        # if duplicate recods of same stock
        elif len(rows) > 1:
            return apology("duplicate held stocks")
        else:
            new_share = int(rows[0]['share']) + share
            db.execute("UPDATE user_stock SET share=:new_share WHERE (id=:user_id AND symbol=:symbol);", 
                new_share=new_share,
                user_id=user_id,
                symbol=stock['symbol'])
        
        # update users
        db.execute("UPDATE users SET cash=:new_cash WHERE ID=:user_id;", new_cash = user_rows[0]["cash"] - cost, user_id = user_id)
        
        return render_template("bought.html", share = share, symbol = stock['symbol'], price = stock['price'] * share)
    
    # user reached route via GET (as by clicking a link or via redirect)
    elif request.method == "GET":
        return render_template("buy.html")
    
    # get the html via neither "POST" nor "GET", something is wrong
    return apology("Unknown request method")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    if request.method == "GET":
        user_id = session["user_id"]
        rows = (db.execute("SELECT * FROM transaction_history WHERE id=:user_id", user_id = user_id))
        transaction_history = []
        for row in rows:
            transacted_symbol = row["symbol"]
            transacted_share = row["share"]
            transacted_price = row["price"]
            transacted_time = row["transacted"]
            item = (transacted_symbol, transacted_share, transacted_price, transacted_time)
            transaction_history.append(item)
        return render_template("history.html", transaction_history = transaction_history)
    else:
        return apology("Invalid request method")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username;", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("quote")
        stock = lookup(symbol)
        if stock == None:
            return apology("Invalid quote")
        else:
            return render_template("quoted.html", name = stock['name'], symbol = stock['symbol'], price = stock['price'])
    
    # user reached route via GET (as by clicking a link or via redirect)
    elif request.method == "GET":
        return render_template("quote.html")
    
    # get the html via neither "POST" nor "GET", something is wrong
    return apology("Unknown request method")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        
        # ensure confirmation password matches password
        elif (request.form.get("password") != request.form.get("confirm_password")):
            return apology("passwords do not match")
        
        # ensure the username is new
        rows = db.execute("SELECT * FROM users WHERE username = :username;", username=request.form.get("username"))
        if len(rows) >= 1:
            return apology("username already exists")
        
        # insert the newuser
        (db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash_value);", 
                username=request.form.get("username"), 
                hash_value= pwd_context.hash(request.form.get("password"))  ))

        # remember which user has logged in
        session["user_id"] = request.form.get("username")
        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    # TODO: render sell.html
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        # if invalid symbol
        if stock == None:
            return apology("Invalid symbol")
        share = int(request.form.get("share"))
        # if invalid share
        if share <= 0:
            return apology("Invalid number of share")
        # valid symbol and share, but if user has insufficient share
        rows = db.execute("SELECT * FROM user_stock WHERE (id = :user_id AND symbol = :symbol)", user_id = user_id, symbol = stock["symbol"])
        if len(rows) > 1:
            return apology("The user has multiple records")
        elif len(rows) == 0:
            return apology("The user does not have this stock")
        
        # user has correctly one record, continue
        if share > int(rows[0]["share"]):
            return apology("Insufficient stocks to sell")
        
        # valid transaction
        (db.execute("INSERT INTO transaction_history (id, symbol, share, price) VALUES (:user_id,:symbol,:share,:price)",
            user_id = user_id, 
            symbol = stock['symbol'],
            share = -share,
            price = stock['price'])
        )
        
        # update user_stock
        new_share = int(rows[0]["share"]) - share
        db.execute("UPDATE user_stock SET share=:new_share WHERE (id=:user_id AND symbol=:symbol);", 
                new_share=new_share,
                user_id=user_id,
                symbol=stock['symbol'])
        
        # update users
        earning = stock["price"] * share
        rows = db.execute("SELECT * FROM users WHERE id=:user_id;", user_id = user_id)
        if len(rows) != 1:
            return apology("Invalid user records")
        new_cash = float(rows[0]["cash"]) + earning
        db.execute("UPDATE users SET cash=:new_cash WHERE ID=:user_id;", new_cash = new_cash, user_id = user_id)
        
        return render_template("sold.html", share = share, symbol = stock['symbol'], price = stock['price'] * share)
    
    # user reached route via GET (as by clicking a link or via redirect)
    elif request.method == "GET":
        return render_template("sell.html")
    
    # get the html via neither "POST" nor "GET", something is wrong
    return apology("Unknown request method")

"""
TODO: 
1. replace bought with index plus alert
2. replace sold with index plus alert
"""
