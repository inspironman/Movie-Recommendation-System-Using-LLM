import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ast

class ContentRecommender:
    def __init__(self, csv_path):
        self.movies_df = pd.read_csv(csv_path)
        self.cosine_sim = self.preprocess_and_compute_similarity()

    def preprocess_and_compute_similarity(self):
        self.movies_df['combined_features'] = (
            self.movies_df['title'].fillna('') + ' ' + 
            self.movies_df['overview'].fillna('') + ' ' +
            self.movies_df['genres'].fillna('') + ' ' + 
            self.movies_df['keywords'].fillna('') + ' ' +
            self.movies_df['cast'].fillna('') + ' ' +
            self.movies_df['crew'].fillna('')
        )
        
        # Create TF-IDF vectors
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(self.movies_df['combined_features'])
        
        return cosine_similarity(tfidf_matrix, tfidf_matrix)

    def get_recommendations(self, title, num_recommendations=10):
        idx = self.movies_df[self.movies_df['title'] == title].index[0]

        sim_scores = list(enumerate(self.cosine_sim[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        sim_scores = sim_scores[1:num_recommendations+1]

        movie_indices = [i[0] for i in sim_scores]

        return self.movies_df['title'].iloc[movie_indices].tolist()

    def get_movie_titles(self):
        return self.movies_df['title'].tolist()

if __name__ == "__main__":
    csv_path = 'D:/MRS/llm-openai/data/filtered_movies_data.csv'
    recommender = ContentRecommender(csv_path)
    print("Number of movies:", len(recommender.get_movie_titles()))
    print("\nRecommendations for 'Avatar':")
    print(recommender.get_recommendations('Avatar'))
 