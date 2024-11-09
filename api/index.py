import os
import sys
import requests
from openai import OpenAI
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.user_operations import *
from src.content_recommender import ContentRecommender

load_dotenv()  # Load environment variables

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_fallback_secret_key_here')
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'filtered_movies_data.csv')

recommender = ContentRecommender(CSV_PATH)

def get_movie_details(movie_title):
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_title}"
    response = requests.get(search_url)
    if response.status_code == 200:
        results = response.json()['results']
        if results:
            movie = results[0]  # Get the first (most relevant) result
            return {
                'title': movie['title'],
                'overview': movie['overview'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie['poster_path'] else None
            }
    return None

@app.route('/')
def index():
    recommendation_type = request.args.get('type')
    return render_template('index.html', recommendation_type=recommendation_type)


@app.route("/genre_based", methods=("GET", "POST"))
def genre_based():
    if request.method == "POST":
        category = request.form["category"]
        number = request.form["number"]
        response = client.chat.completions.create(
            model="gpt-4o-mini",   
            messages=[
                {"role": "system", "content": "You are a helpful assistant that recommends movies. Respond only with the titles of the movies, one per line."},
                {"role": "user", "content": generate_genre_based_prompt(number, category)}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        movie_titles = response.choices[0].message.content.strip().split('\n')
        movie_details = []
        for title in movie_titles:
            details = get_movie_details(title)
            if details:
                movie_details.append(details)

        return render_template("index.html", movies=movie_details)

    return render_template("index.html", movies=None)


def generate_mood_based_prompt(number, mood):
    return f"Suggest exactly {number} movies that are good to watch when feeling {mood}. Only list the movie titles, one per line."

@app.route("/mood_based", methods=("GET", "POST"))
def mood_based():
    if request.method == "POST":
        mood = request.form["mood"]
        number = int(request.form["number"])  # Convert to integer
        response = client.chat.completions.create(
            model="gpt-4o-mini",   
            messages=[
                {"role": "system", "content": "You are a helpful assistant that recommends movies. Respond only with the titles of the movies, one per line. Do not include any additional text or numbering."},
                {"role": "user", "content": generate_mood_based_prompt(number, mood)}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        movie_titles = response.choices[0].message.content.strip().split('\n')
        # Ensure we only take the requested number of movies
        movie_titles = movie_titles[:number]
        
        movie_details = []
        for title in movie_titles:
            details = get_movie_details(title)
            if details:
                movie_details.append(details)

        return render_template("index.html", movies=movie_details)

    return render_template("index.html", movies=None)



@app.route('/content_based', methods=['GET', 'POST'])
def content_based():
    if request.method == 'POST':
        movie = request.form['movie']
        number = int(request.form['number'])
        
        # Check if the movie exists in our dataset
        if movie not in recommender.get_movie_titles():
            error_message = f"Sorry, '{movie}' is not in our database. Please try another movie."
            return render_template('index.html', recommendation_type='content', error_message=error_message)
        
        try:
            # Get recommendations using your ContentRecommender
            recommended_titles = recommender.get_recommendations(movie, number)
            
            # Fetch details for each recommended movie from TMDB
            movies = []
            for title in recommended_titles:
                details = get_movie_details(title)
                if details:
                    movies.append(details)
            
            return render_template('index.html', recommendation_type='content', movies=movies)
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            return render_template('index.html', recommendation_type='content', error_message=error_message)
    
    return render_template('index.html', recommendation_type='content')



def generate_genre_based_prompt(number, category):
    return f"""Recommend the best {number} {category.capitalize()} movies to watch. List only the titles, one per line:"""

def generate_mood_based_prompt(number, category):
    return f"""Recommend the best movies to watch. If a person is feeling {category.capitalize()}"""

@app.route('/register', methods=['POST'])
def register():
    if request.content_type == 'application/json':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
    else:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
    
    if not all([username, email, password]):
        return jsonify({"error": "Missing required fields"}), 400
    
    result = register_user(username, email, password)
    if result == "User registered successfully":
        flash("Registration successful! You can now log in.", "success")
        return jsonify({"message": result}), 201
    else:
        flash(result, "error")
        return jsonify({"error": result}), 400


@app.route('/login', methods=['POST'])
def login():
    if request.content_type == 'application/json':
        data = request.json
        username = data.get('username')
        password = data.get('password')
    else:
        username = request.form.get('username')
        password = request.form.get('password')
    
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400
    
    user = authenticate_user(username, password)
    
    if user:
        session['user_id'] = user['id']  # Set user_id in session
        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email']
                # Add any other non-sensitive user details you want to return
            }
        }), 200
    else:
        return jsonify({"error": "Invalid username or password"}), 401


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logged out successfully"}), 200


@app.route('/check_login')
def check_login():
    if 'user_id' in session:
        return jsonify({"logged_in": True, "user_id": session['user_id']}), 200
    else:
        return jsonify({"logged_in": False}), 200
    

@app.route('/top_rated', methods=['GET'])
def top_rated_movies():
    # TMDb API endpoint to get top-rated movies
    top_rated_url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=en-US&page=1"
    response = requests.get(top_rated_url)
    
    if response.status_code == 200:
        movies = response.json()['results']
        movie_details = []
        for movie in movies:
            movie_details.append({
                'title': movie['title'],
                'overview': movie['overview'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie['poster_path'] else None
            })
        
        return render_template('index.html', movies=movie_details, recommendation_type='top_rated')
    else:
        flash('Error fetching top rated movies', 'error')
        return render_template('index.html')

@app.route('/trending', methods=['GET'])
def trending_movies():
    # TMDb API endpoint to get trending movies
    trending_url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}&language=en-US"
    response = requests.get(trending_url)
    
    if response.status_code == 200:
        movies = response.json()['results']
        movie_details = []
        for movie in movies:
            movie_details.append({
                'title': movie['title'],
                'overview': movie['overview'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie['poster_path'] else None
            })
        
        return render_template('index.html', movies=movie_details, recommendation_type='trending')
    else:
        flash('Error fetching trending movies', 'error')
        return render_template('index.html')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=True)
