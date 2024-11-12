import os
import sys
import requests
from openai import OpenAI
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
import logging
from flask_caching import Cache

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
app.config['CACHE_TYPE'] = 'SimpleCache'  
cache = Cache(app)
recommender = ContentRecommender(CSV_PATH)


@cache.memoize(timeout=3600)
def get_movie_details(movie_id):
    """Fetches additional details like runtime, director, and trailer for a given movie ID."""
    details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
    details_response = requests.get(details_url)
    runtime = None
    director = "Unknown"
    trailer_link = None
    
    if details_response.status_code == 200:
        movie_details = details_response.json()
        
        # Extract runtime
        runtime = movie_details.get('runtime')
        
        # Get the director's name from the credits endpoint
        credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={TMDB_API_KEY}"
        credits_response = requests.get(credits_url)
        if credits_response.status_code == 200:
            crew = credits_response.json().get('crew', [])
            for member in crew:
                if member['job'] == 'Director':
                    director = member['name']
                    break

        # Get trailer link from the videos endpoint
        videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}"
        videos_response = requests.get(videos_url)
        if videos_response.status_code == 200:
            videos = videos_response.json().get('results', [])
            for video in videos:
                if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                    trailer_link = f"https://www.youtube.com/watch?v={video['key']}"
                    break

    return runtime, director, trailer_link

def get_movie_details_by_title(movie_title):
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_title}"
    response = requests.get(search_url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        if results:
            movie = results[0]  # Get the first result
            return {
                'id': movie['id'],
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
    username = session.get('username')
    return render_template('index.html', recommendation_type=recommendation_type, username=username)



@app.route("/genre_based", methods=["GET", "POST"])
def genre_based():
    if request.method == "POST":
        category = request.form["category"]
        number = int(request.form["number"])
        
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
            # Fetch movie details by title to get the movie ID first
            movie_info = get_movie_details_by_title(title)
            if movie_info:
                movie_id = movie_info.get('id')
                
                # Get basic movie info
                movie_details.append({
                    'title': movie_info['title'],
                    'overview': movie_info['overview'],
                    'release_date': movie_info['release_date'],
                    'vote_average': movie_info['vote_average'],
                    'poster_path': movie_info['poster_path'],
                    'genre': [],  # You'll need to get this from additional API call
                    'runtime': 'N/A',  # You'll need to get this from additional API call
                    'director': 'N/A',  # You'll need to get this from additional API call
                    'trailer_link': None  # You'll need to get this from additional API call
                })

                # Get additional details
                try:
                    details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=credits,videos"
                    details_response = requests.get(details_url)
                    if details_response.status_code == 200:
                        movie_details_data = details_response.json()
                        
                        # Update with additional information
                        movie_details[-1].update({
                            'genre': [genre['name'] for genre in movie_details_data.get('genres', [])],
                            'runtime': movie_details_data.get('runtime', 'N/A'),
                            'director': next((crew['name'] for crew in movie_details_data.get('credits', {}).get('crew', []) 
                                           if crew['job'] == 'Director'), 'N/A'),
                            'trailer_link': next((f"https://www.youtube.com/watch?v={video['key']}" 
                                                for video in movie_details_data.get('videos', {}).get('results', [])
                                                if video['type'] == 'Trailer'), None)
                        })
                except Exception as e:
                    print(f"Error getting additional details: {e}")

        return render_template("index.html", movies=movie_details, recommendation_type='genre_based')

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('index.html', show_register_modal=True)

        # Try to register the user
        result = register_user(username, email, password)
        
        if result == "User registered successfully":
            # If registration successful, authenticate and log in
            user = authenticate_user(username, password)
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Registration successful! Welcome to Movie Recommender!', 'success')
                return redirect(url_for('index'))
        else:
            # If registration failed, show error
            flash(result, 'error')
            return render_template('index.html', 
                                show_register_modal=True,
                                reg_username=username,
                                reg_email=email)

    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Missing username or password', 'error')
            return render_template('index.html', show_login_modal=True)
        
        user = authenticate_user(username, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            # Pass show_login_modal=True to keep the modal open
            return render_template('index.html', 
                                show_login_modal=True, 
                                login_username=username)

    return redirect(url_for('index'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/check_login')
def check_login():
    if 'user_id' in session:
        return jsonify({"logged_in": True, "user_id": session['user_id']}), 200
    else:
        return jsonify({"logged_in": False}), 200
    

genre_map = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}

@app.route('/top_rated', methods=['GET'])
def top_rated_movies():
    page = request.args.get('page', 1, type=int)  # Get the page parameter from the request
    top_rated_url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=en-US&page={page}"
    response = requests.get(top_rated_url)
    
    if response.status_code == 200:
        movies = response.json()['results']
        movie_details = []
        for movie in movies:
            genres = [genre_map[genre_id] for genre_id in movie['genre_ids'] if genre_id in genre_map]
            runtime, director, trailer_link = get_movie_details(movie['id'])
            movie_details.append({
                'title': movie['title'],
                'overview': movie['overview'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie['poster_path'] else None,
                'genre': genres,
                'runtime': runtime,         # Add runtime to movie details
                'director': director,       # Add director to movie details
                'trailer_link': trailer_link  # Add trailer link to movie details
            })
        
        if request.headers.get('Accept') == 'application/json':
            return jsonify(movies=movie_details)
        
        return render_template('index.html', movies=movie_details, recommendation_type='trending')
    else:
        flash('Error fetching trending movies', 'error')
        return render_template('index.html')


@app.route('/trending', methods=['GET'])
def trending_movies():
    page = request.args.get('page', 1, type=int)
    trending_url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}&language=en-US&page={page}"
    response = requests.get(trending_url)
    
    if response.status_code == 200:
        movies = response.json()['results']
        movie_details = []
        for movie in movies:
            genres = [genre_map[genre_id] for genre_id in movie['genre_ids'] if genre_id in genre_map]
            runtime, director, trailer_link = get_movie_details(movie['id'])
            movie_details.append({
                'title': movie['title'],
                'overview': movie['overview'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie['poster_path'] else None,
                'genre': genres,
                'runtime': runtime,         # Add runtime to movie details
                'director': director,       # Add director to movie details
                'trailer_link': trailer_link  # Add trailer link to movie details
            })
        
        if request.headers.get('Accept') == 'application/json':
            return jsonify(movies=movie_details)
        
        return render_template('index.html', movies=movie_details, recommendation_type='trending')
    else:
        flash('Error fetching trending movies', 'error')
        return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=True)
