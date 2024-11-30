import os
import sys
import requests
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from flask_caching import Cache
from dotenv import load_dotenv
import logging
import openai

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add project directories to sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.user_operations import register_user, authenticate_user
from src.content_recommender import ContentRecommender


class MovieRecommenderApp:
    def __init__(self):
        load_dotenv()  # Load environment variables

        # Initialize Flask app
        self.app = Flask(__name__)
        self.app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_fallback_secret_key_here')
        self.app.config['CACHE_TYPE'] = 'SimpleCache'
        self.cache = Cache(self.app)

        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.TMDB_API_KEY = os.getenv("TMDB_API_KEY")
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'filtered_movies_data.csv'
        )
        self.recommender = ContentRecommender(csv_path)

        # Map genres
        self.genre_map = {
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

        # Define routes
        self.define_routes()

    def define_routes(self):
        app = self.app  # To access app within nested functions

        @app.route('/')
        def index():
            recommendation_type = request.args.get('type')
            username = session.get('username')
            return render_template('index.html', recommendation_type=recommendation_type, username=username)

        @app.route("/genre_based", methods=["GET", "POST"])
        def genre_based():
            return self.genre_based()

        @app.route("/mood_based", methods=["GET", "POST"])
        def mood_based():
            return self.mood_based()

        @app.route('/content_based', methods=['GET', 'POST'])
        def content_based():
            return self.content_based()

        @app.route('/register', methods=['GET', 'POST'])
        def register():
            return self.register()

        @app.route('/login', methods=['GET', 'POST'])
        def login():
            return self.login()

        @app.route('/logout', methods=['POST'])
        def logout():
            return self.logout()

        @app.route('/check_login')
        def check_login():
            return self.check_login()

        @app.route('/top_rated', methods=['GET'])
        def top_rated_movies():
            return self.top_rated_movies()

        @app.route('/trending', methods=['GET'])
        def trending_movies():
            return self.trending_movies()

    def get_movie_details(self, movie_id):
        """Fetches additional details like runtime, director, and trailer for a given movie ID."""
        @self.cache.memoize(timeout=3600)
        def fetch_details(movie_id):
            details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={self.TMDB_API_KEY}"
            details_response = requests.get(details_url)
            runtime = None
            director = "Unknown"
            trailer_link = None
            
            if details_response.status_code == 200:
                movie_details = details_response.json()
                
                # Extract runtime
                runtime = movie_details.get('runtime')
                
                # Get the director's name from the credits endpoint
                credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={self.TMDB_API_KEY}"
                credits_response = requests.get(credits_url)
                if credits_response.status_code == 200:
                    crew = credits_response.json().get('crew', [])
                    for member in crew:
                        if member['job'] == 'Director':
                            director = member['name']
                            break

                # Get trailer link from the videos endpoint
                videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.TMDB_API_KEY}"
                videos_response = requests.get(videos_url)
                if videos_response.status_code == 200:
                    videos = videos_response.json().get('results', [])
                    for video in videos:
                        if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                            trailer_link = f"https://www.youtube.com/watch?v={video['key']}"
                            break

            return runtime, director, trailer_link

        return fetch_details(movie_id)


    """This function fetches the details of a movie by its title using the TMDb API."""
    def get_movie_details_by_title(self, movie_title):
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={self.TMDB_API_KEY}&query={movie_title}"
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


    """This function generates a prompt for the user to recommend movies based on a genre."""
    def generate_genre_based_prompt(self,number, category):
        return f"""Recommend the best {number} {category.capitalize()} movies to watch. List only the titles, one per line:"""

    """This function generates a prompt for the user to recommend movies based on a mood."""
    def generate_mood_based_prompt(self,number, category):
        return f"""Recommend the best {number} movies to watch. If a person is feeling {category.capitalize()}"""

    """This function fetches a list of movie titles from a prompt."""
    def get_movie_titles_from_prompt(self, number, prompt_content):
        """
        Get a list of movie titles from a prompt.
        """
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that recommends movies. Respond only with the titles of the movies, one per line."},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        movie_titles = response.choices[0].message.content.strip().split('\n')
        return movie_titles[:number]

    """This function fetches detailed information for a movie by title from TMDb."""
    def fetch_movie_details(self, title):
        """
        Fetches detailed information for a movie by title from TMDb.
        """
        movie_info = self.get_movie_details_by_title(title)
        if not movie_info:
            return None
        
        movie_id = movie_info.get('id')
        movie_detail = {
            'title': movie_info['title'],
            'overview': movie_info['overview'],
            'release_date': movie_info['release_date'],
            'vote_average': movie_info['vote_average'],
            'poster_path': movie_info['poster_path'],
            'genre': [],
            'runtime': 'N/A',
            'director': 'N/A',
            'trailer_link': None
        }
        
        # Fetch additional details using TMDb API
        try:
            details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={self.TMDB_API_KEY}&append_to_response=credits,videos"
            details_response = requests.get(details_url)
            if details_response.status_code == 200:
                movie_details_data = details_response.json()
                
                # Update movie details with extended information
                movie_detail.update({
                    'genre': [genre['name'] for genre in movie_details_data.get('genres', [])],
                    'runtime': movie_details_data.get('runtime', 'N/A'),
                    'director': next((crew['name'] for crew in movie_details_data.get('credits', {}).get('crew', []) 
                                    if crew['job'] == 'Director'), 'N/A'),
                    'trailer_link': next((f"https://www.youtube.com/watch?v={video['key']}" 
                                        for video in movie_details_data.get('videos', {}).get('results', [])
                                        if video['type'] == 'Trailer'), None)
                })
        except Exception as e:
            print(f"Error getting additional details for '{title}': {e}")

        return movie_detail
    
    def genre_based(self):
        username = session.get('username')
        if request.method == "POST":
            category = request.form["category"]
            number = int(request.form["number"])
            prompt_content = self.generate_genre_based_prompt(number, category)
            movie_titles = self.get_movie_titles_from_prompt(number, prompt_content)
            
            movie_details = [self.fetch_movie_details(title) for title in movie_titles if self.fetch_movie_details(title)]
            return render_template("index.html", movies=movie_details,  username=username, recommendation_type='genre_based')
        
        return render_template("index.html", movies=None, username=username, recommendation_type="genre_based")


    def mood_based(self):
        username = session.get('username')
        if request.method == "POST":
            mood = request.form["mood"]
            number = int(request.form["number"])
            prompt_content = self.generate_mood_based_prompt(number, mood)
            movie_titles = self.get_movie_titles_from_prompt(number, prompt_content)
            
            movie_details = [self.fetch_movie_details(title) for title in movie_titles if self.fetch_movie_details(title)]
            return render_template("index.html", movies=movie_details, username=username, recommendation_type="mood_based")
        
        return render_template("index.html", movies=None, username=username)

    def content_based(self):
        username = session.get('username')
        if request.method == 'POST':
            movie = request.form['movie']
            number = int(request.form['number'])
            
            # Check if the movie exists in the dataset
            if movie not in self.recommender.get_movie_titles():
                error_message = f"Sorry, '{movie}' is not in our database. Please try another movie."
                return render_template('index.html', recommendation_type='content_based', error_message=error_message, username=username)
            
            try:
                # Get recommendations using the ContentRecommender
                recommended_titles = self.recommender.get_recommendations(movie, number)
                movie_details = [self.fetch_movie_details(title) for title in recommended_titles if self.fetch_movie_details(title)]
                
                return render_template('index.html', recommendation_type='content_based', movies=movie_details, username=username)
            
            except Exception as e:
                error_message = f"An error occurred: {str(e)}"
                return render_template('index.html', recommendation_type='content_based', username=username)
        
        return render_template('index.html', username=username, recommendation_type="content_based")
    
    def register(self):
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
                flash(result, 'register_error')
                return render_template('index.html', 
                                    show_register_modal=True,
                                    reg_username=username,
                                    reg_email=email)

        return redirect(url_for('index'))


    def login(self):
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
                flash('Invalid username or password', 'login_error')
                # Pass show_login_modal=True to keep the modal open
                return render_template('index.html', 
                                    show_login_modal=True, 
                                    login_username=username)

        return redirect(url_for('index'))



    def logout(self):
        session.clear()
        return redirect(url_for('index'))


    def check_login(self):
        if 'user_id' in session:
            return jsonify({"logged_in": True, "user_id": session['user_id']}), 200
        else:
            return jsonify({"logged_in": False}), 200
    

    def top_rated_movies(self):
        page = request.args.get('page', 1, type=int)  # Get the page parameter from the request
        top_rated_url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={self.TMDB_API_KEY}&language=en-US&page={page}"
        response = requests.get(top_rated_url)
        username = session.get('username')
        if response.status_code == 200:
            movies = response.json()['results']
            movie_details = []
            for movie in movies:
                genres = [self.genre_map[genre_id] for genre_id in movie['genre_ids'] if genre_id in self.genre_map]
                runtime, director, trailer_link = self.get_movie_details(movie['id'])
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
            
            return render_template('index.html', movies=movie_details, recommendation_type='trending', username=username)
        else:
            flash('Error fetching trending movies', 'error')
            return render_template('index.html', username=username)
    
    def trending_movies(self):
            page = request.args.get('page', 1, type=int)
            trending_url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={self.TMDB_API_KEY}&language=en-US&page={page}"
            response = requests.get(trending_url)
            username = session.get('username')
            if response.status_code == 200:
                movies = response.json()['results']
                movie_details = []
                for movie in movies:
                    genres = [self.genre_map[genre_id] for genre_id in movie['genre_ids'] if genre_id in self.genre_map]
                    runtime, director, trailer_link = self.get_movie_details(movie['id'])
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
                
                return render_template('index.html', movies=movie_details, recommendation_type='trending', username=username)
            else:
                flash('Error fetching trending movies', 'error')
                return render_template('index.html', username=username)

    def run(self, host="0.0.0.0", port=8080, debug=True):
        self.app.run(host=host, port=port, debug=debug)


# Instantiate and run the app
if __name__ == '__main__':
    app = MovieRecommenderApp()
    app.run(debug=True)
