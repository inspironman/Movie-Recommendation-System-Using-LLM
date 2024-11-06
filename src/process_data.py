import pandas as pd
import ast

def load_datasets(movies_path, credits_path):
    """
    Load the movies and credits datasets from CSV files.
    :param movies_path: Path to the movies dataset
    :param credits_path: Path to the credits dataset
    :return: Merged DataFrame
    """
    movies_df = pd.read_csv(movies_path)
    credits_df = pd.read_csv(credits_path)
    
    merged_df = movies_df.merge(credits_df, on='title')
    
    print("Columns in merged DataFrame:", merged_df.columns.tolist())
    
    return merged_df


def convert(text):
    L = []
    for i in ast.literal_eval(text):
        L.append(i['name']) 
    L = ' '.join(L)
    return L 


def convert3(text):
    L = []
    counter = 0
    for i in ast.literal_eval(text):
        if counter < 3:
            L.append(i['name'])
        counter+=1
    return L 


def fetch_director(text):
    L = []
    for i in ast.literal_eval(text):
        if i['job'] == 'Director':
            L.append(i['name'])
    return L 


def filter_columns(merged_df):
    """
    Filter the merged DataFrame to keep only the necessary columns.
    :param merged_df: Merged DataFrame from movies and credits datasets
    :return: Filtered DataFrame
    """
    print("Columns in merged DataFrame:", merged_df.columns.tolist())
    
    filtered_df = merged_df[['movie_id', 'title', 'overview','genres', 'keywords', 'vote_average', 'vote_count', 'popularity', 'release_date', 'cast', 'crew']]
    filtered_df.dropna(inplace=True)
    filtered_df['genres'] = filtered_df['genres'].apply(convert)
    filtered_df['keywords'] = filtered_df['keywords'].apply(convert)
    filtered_df['cast'] = filtered_df['cast'].apply(convert3)
    filtered_df['crew'] = filtered_df['crew'].apply(fetch_director)

    return filtered_df



def save_filtered_data(filtered_df, output_path):
    """
    Save the filtered DataFrame to a CSV file.
    :param filtered_df: DataFrame with filtered columns
    :param output_path: Path where the filtered data will be saved
    """
    filtered_df.to_csv(output_path, index=False)
    print(f"Filtered data saved to {output_path}")

if __name__ == "__main__":
    movies_path = 'D:/MRS/llm-openai/data/tmdb_5000_movies.csv'
    credits_path = 'D:/MRS/llm-openai/data/tmdb_5000_credits.csv'
    output_path = 'D:/MRS/llm-openai/data/filtered_movies_data.csv'

    merged_df = load_datasets(movies_path, credits_path)
    
    filtered_df = filter_columns(merged_df)
    
    save_filtered_data(filtered_df, output_path)
