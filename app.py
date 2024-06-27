import streamlit as st
import os
import pandas as pd
import streamlit as st
import time
import spotipy
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth

#Credentials
#Spotify API credentials
# CLIENT_ID = '<INSERT ID>'
# CLIENT_SECRET = '<INSERT SECRET>'
CLIENT-ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
port = int(os.environ.get('PORT', 8888))
redirect_uri = f'https://share.streamlit.io/nanfographics/pyotr-playlist'

# Authenticate with Spotify
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=redirect_uri, scope='user-read-private user-top-read')
sp = spotipy.Spotify(auth_manager=sp_oauth)


#HELPER FUNCTIONS

#Authentication
def authenticate_user():
    global sp
    #User Information
    if sp.current_user() is not None: #If a session exists
        user = sp.current_user()
        st.success(f"Successfully authenticated as {user['display_name']}")
        st.write(f"Your Spotify Profile: {user['external_urls']['spotify']}")

    elif sp.current_user() is None: #If a user session needs to be launched
            auth_url = sp_oauth.get_authorize_url() 
            st.write('Click the link below to log into your Spotify')
            st.markdown(f"[**Login with Spotify**]({auth_url})") #Display Link to get authorized
            redirect_url = st.text_input("Paste the redirect URL here:")

            if redirect_url is not None:
                code = sp_oauth.parse_response_code(redirect_url)
                token_info = sp_oauth.get_access_token(code)
                if 'access_token' in token_info:
                    access_token = token_info['access_token']
                    sp = spotipy.Spotify(auth=access_token)
                    user = sp.current_user()
                    st.success(f"Successfully authenticated as {user['display_name']}")
                    st.write(f"Your Spotify Profile: {user['external_urls']['spotify']}")
                else:
                    st.error("Failed to obtain access token.")

    return True

#Function to unpack Name, ID, URI for artists and Release Date,
def get_attributes(row):
    
    release_dt = row['album'].get('release_date')
    
    artistinfo = []  
    
    for artist in row['album'].get('artists'):
        
        name = artist.get('name')
        id = artist.get('id')
        uri = artist.get('uri')
        
        artistinfo.append([name, id, uri])
    
    return [artistinfo, release_dt]
        
#Function to flatten top track response
def top_track_response(response):

    if 'items' in response.keys():
        tracks = pd.DataFrame(response['items'])
    else:
        tracks = pd.DataFrame(response['tracks'])

    tracks['flat'] = tracks.apply(get_attributes,axis=1)


    return tracks

#Function to Retrieve Genres based on Artist IDs
def get_artist_genres(artist_ids):  
    artists_info = pd.DataFrame()
    # Split artist IDs into batches of 50 (maximum allowed by Spotify API)
    batch_size = 50
    
    for i in range(0, len(artist_ids), batch_size):
        batch_ids = artist_ids[i:i + batch_size]     
        
        # Get artist information for the batch of IDs
        artists_info = pd.concat([artists_info,pd.DataFrame(sp.artists(batch_ids)['artists'])])
        
            
    return artists_info

#Function to Retrieve Audio Features
def get_audio_features(track_ids):
 
    dance, energy, valence = [], [], []
    
    batch_size = 100
    
    for i in range(0,len(track_ids),batch_size):
        
        batch_ids = track_ids[i:i + batch_size]
        aud_feat = sp.audio_features(batch_ids)
        
        for feat in aud_feat:
            if feat is not None:
                dance.append(feat['danceability'])
                energy.append(feat['energy'])
                valence.append(feat['danceability'])
            else:
                dance.append(0)
                energy.append(0)
                valence.append(0)
    
    print('Done!')
    return dance, energy, valence

#Functions to get unique song and artist when aggregating final playlist
def unique_names(x):
#    st.write("Input values:" + str(x))
    unique_names_set = set(x)
#    st.write("Processed vals:" + str(unique_names_set))
    return ', '.join(unique_names_set)


#Generate Universe of Songs
@st.cache_data
def generate_uni():

    #Make Request for User's Top Tracks and Unpack Response
    user_toptrack = sp.current_user_top_tracks(time_range='medium_term', limit=50)
    your_tops = top_track_response(user_toptrack)
    your_tops['artists_flat'] = your_tops['flat'].str[0]
    your_tops['release_date'] = your_tops['flat'].str[1]

    your_tops['artists_flat'] = your_tops['flat'].str[0]
    your_tops['release_date'] = your_tops['flat'].str[1]

    #Manipulate Users Top Tracks Response
    your_tops = your_tops.drop(columns=['flat'])
    your_tops['artists_names'] = your_tops['artists_flat'].apply(lambda x: [artist[0] for artist in x])
    your_tops['artists_ids'] = your_tops['artists_flat'].apply(lambda x: [artist[1] for artist in x])
    your_tops = your_tops.explode(['artists_names','artists_ids'])
    your_tops = your_tops.reset_index(drop=True)
    
    #Get Genres for User's Top Tracks
    artist_ids = your_tops['artists_ids'].tolist()
    genres = get_artist_genres(artist_ids)
    genres = genres[['id','genres']]
    genres = genres.drop_duplicates(subset='id', keep='first')
    genres = genres.reset_index(drop=True)
    
    #Merge User's Top Tracks with Genres
    your_tops = your_tops.merge(genres, left_on='artists_ids',right_on='id',how='outer')
    your_tops = your_tops.drop(columns=['id_y']).rename(columns={'id_x':'id'})
    
    artist_toptracks = pd.DataFrame()

    #Batch off artist IDs to get their top tracks
    for i in range(0, len(your_tops['artists_ids'])):

        toptracks = sp.artist_top_tracks(your_tops['artists_ids'][i])
        toptracks = top_track_response(toptracks).reset_index(drop=True)
        artist_toptracks = pd.concat([artist_toptracks,toptracks],axis=0)

    artist_toptracks = artist_toptracks.reset_index(drop=True)
    
    #Manipulate Artists' Top Tracks Response
    artist_toptracks['artists_flat'] = artist_toptracks['flat'].str[0]
    artist_toptracks['release_date'] = artist_toptracks['flat'].str[1]
    artist_toptracks = artist_toptracks.drop(columns=['flat'])
    artist_toptracks['artists_names'] = artist_toptracks['artists_flat'].apply(lambda x: [artist[0] for artist in x])
    artist_toptracks['artists_ids'] = artist_toptracks['artists_flat'].apply(lambda x: [artist[1] for artist in x])
    artist_toptracks = artist_toptracks.explode(['artists_names','artists_ids'])
    artist_toptracks = artist_toptracks.reset_index(drop=True)
    
    #Get Genres for Artists' Top Tracks
    artist_tops_ids = artist_toptracks['artists_ids'].tolist()
    genres = get_artist_genres(artist_tops_ids)
    genres = genres[['id','genres']]
    genres = genres.drop_duplicates(subset='id', keep='first')
    
    #Merge Artists' Top Tracks with Genres
    artist_toptracks = artist_toptracks.merge(genres, left_on='artists_ids',right_on='id',how='outer')
    artist_toptracks = artist_toptracks.drop(columns=['id_y']).rename(columns={'id_x':'id'})
    
    #Final Universe of Tracks to Generate Playlist From
    playlist_universe = pd.concat([your_tops,artist_toptracks],ignore_index=True)
    playlist_universe['name'] = playlist_universe['name'].astype('str')
    
    #Store Song name map
    song_name_map = playlist_universe[['id','name']].drop_duplicates()
    
    #Group by Song Name to get Unique Song Playlist
    # Define aggregation functions
    aggregations = {
        #'id': lambda x: ', '.join(set(', '.join(x).split(', '))),
        'artists_ids': lambda x: ', '.join(x),
        'genres': 'sum',
        'artists_names': lambda x: ', '.join(map(str, pd.Series(x).drop_duplicates()))
    }

    unique_universe = playlist_universe.groupby('id').agg(aggregations).reset_index()

    #Get Audio Features for Unique Song Playlist
    tracks = list(unique_universe['id'])
    unique_universe['danceability'], unique_universe['energy'], unique_universe['valence'] = get_audio_features(tracks)
    
    return unique_universe, song_name_map

#Function to Filter Playlist based on Selections
def filter_playlist(df,valence,dance,activity):
    
    mapping = {} 
    
    if valence:
        mapping = {
            'Bad': (0.0,0.4999),
            'Good': (0.5,1.0)
        }
        val_min, val_max = mapping.get(valence, (0.0,1.0))
        
    if dance:
        mapping = {
             1: (0.0, 0.2),
             2: (0.2, 0.4),
             3: (0.4, 0.6),
             4: (0.6, 0.8),
             5: (0.8, 1.0)
        } 
        dance_min, dance_max = mapping.get(dance, (0.0,1.0))
    
    if activity:
        mapping = {
             'Solo Chill': (0.0, 0.299),
             'Chill with Friends': (0.3, 0.499),
             'Social Gathering': (0.5, 0.699),
             'Party': (0.7, 0.899),
             'Rager': (0.9, 1.0)
        } 
        act_min, act_max = mapping.get(activity, (0.0,1.0))
    
    df = df[(df['valence'] > val_min) & (df['valence'] < val_max)]
    df = df[(df['danceability'] > dance_min) & (df['danceability'] < dance_max)]
    df = df[(df['energy'] > act_min) & (df['energy'] < act_max)]
    df = df.reset_index(drop=True)

    return df

#Define Function to Ensure 15 song Playlist
def fifteen_songs(unique_universe,result_playlist):
    #Retrieving list of current unique genres in dataset
    if len(result_playlist) > 0:
        flat_genres = []

        for sublist in result_playlist['genres']:
            flat_genres.extend(sublist)

        flat_genres = list(set(flat_genres)) #Storing as variable
    else:
        flat_genres = ['pop','rap','hip hop']
       
    
    r_index = 0 #row index
    l_index = 0 #
    filter_genre = flat_genres[l_index] #current genre we are filtering for
    uni_parsed = len(unique_universe)#number of rows to parse through

    #Checking if we've parsed through all rows yet 
    while uni_parsed >= 0:
        for genres in unique_universe['genres']:
            uni_parsed -= 1
            r_index += 1
            for item in genres:
                if item==filter_genre:
                    row = pd.DataFrame(unique_universe.iloc[r_index]).transpose()
                    result_playlist = pd.concat([result_playlist,row],ignore_index=True)
                    break
            #Checking length of result playlist/uni parsed
            if len(result_playlist) >= 15:
                uni_parsed = -1
                break
        break

    return result_playlist


#Function to Write Playlist to Spotify
def write_playlist(dataframe, playlistname):
    songs = list(dataframe['id'])
    
    playlist = sp.user_playlist_create(user=sp.current_user()['id'], name=playlistname,public=False)
    playlist = sp.playlist_add_items(playlist_id=playlist['id'], items=songs)
    
    if playlist:
        st.text("Pyotr has written your playlist to your account. You are welcome.")


#My Streamlit App:
def main():
    # App Headers
    st.title("PYOTR")
    st.write("PYOTR: Personalized Yet Optimal Track Recommender is the premier playlist generator for all your playlist generating needs. Enter your preferences and Pyotr will generate a perfect playlist for you. :rocket:")
    st.text("*NOTE: This is v1.0 of an app that I am still building - Ananya*")
    
   
    authenticated = authenticate_user()
    
    if authenticated:
        st.text('Authentication successful. Please make selections on the sidebar.')
        
        

    # Sidebar Characteristics
    st.sidebar.title('Playlist Filters')
    playlist_name = st.sidebar.text_input('Give Pyotr a Playlist Name:',None)
    st.sidebar.subheader("Please tell Pyotr what you're looking for...")
    selected_mood = st.sidebar.selectbox('Select your mood:', ['Good', 'Bad'], index=None)
    selected_dance = st.sidebar.slider('On a scale of 1 to 5, how much do you want to dance?', 0, 5, 0)
    selected_activity = st.sidebar.radio('Select the activity', ('Solo Chill','Hanging with Friends','Social Gathering', 'Party', 'Rager'),index=None)
    run_button = st.sidebar.button('Run')

    
    if run_button and not selected_mood and not selected_dance and not selected_activity:
        st.text('You need to make selections before Pyotr can make your playlist...')
    
    #Actions that happen after user makes selections and hits run
    if run_button:
        st.text('Working on your playlist...')
        user_songs, song_name_map = generate_uni()
        
        filtered_songs = filter_playlist(user_songs,selected_mood,selected_dance,selected_activity)

        if len(filtered_songs) < 15:
            filtered_songs = fifteen_songs(user_songs, filtered_songs)
            write_playlist(filtered_songs, playlist_name)
            st.write(filtered_songs.merge(song_name_map, on='id',how='inner')[['name','artists_names']])
            





# Initialize session state variables
# if 'authenticated' not in st.session_state:
#     st.session_state.authenticated = False
# if 'mood_selected' not in st.session_state:
#     st.session_state.mood_selected = False
# if 'dance_selected' not in st.session_state:
#     st.session_state.dance_selected = False

# def main():
#     # App Headers
#     st.title("# Pyotr Burkhe Playlist Generator")
#     st.write("Trying to catch a vibe but too lazy to pick a tune? Enter your preferences and Pyotr Burkhe will generate a playlist perfect for you. :rocket:")
#     st.write("*NOTE: This is v1.0 of an app that I am still building - Ananya*")

#     # Placeholder for Authentication Status
#     authentication_status = st.empty()

#     # Authenticate User
#     if not st.session_state.authenticated:
#         if authentication_status.button('Authenticate User'):
#             st.session_state.authenticated = authenticate_user()

#             st.header('Playlist Filters')
#             st.text("Tell me more about what you're looking for...")

#     # Ask User for Preferences
#     if st.session_state.authenticated and not st.session_state.mood_selected and not st.session_state.dance_selected:
        
#         #Generate Playlist
#         st.session_state['user_songs'] = generate_uni()
        
#         # Mood (Valence) Selection
#         mood_options = ['Good', 'Bad']
#         #mood_selection = st.empty()
#         selected_mood = st.selectbox('Select your mood:', mood_options, index=None)

#         if selected_mood:
#             st.session_state.mood_selected = True
#             st.write(f'You selected: {selected_mood}')
#             val_min, val_max = val_mapping.get(selected_mood, (0.0, 1.0))
#             st.session_state.user_songs = st.session_state.user_songs[(st.session_state.user_songs['valence'] > val_min) & (st.session_state.user_songs['valence'] < val_max)]
            
#             #Dance Selection
#             dance_options = [0,1,2,3,4,5]
#             #dance_selection = st.empty()
#             selected_dance = st.select_slider('On a scale of 1 to 5, how much do you want to dance?',dance_options,value=0)
            
#             if selected_dance:
#                 st.session_state.dance_selected = True
#                 st.write(f'You selected: {selected_dance}')
#                 st.write(st.session_state.user_songs)
           


#             elif valence_2.button('Bad'):
#                 val_min, val_max = valence_mapping.get('Bad', (0.0, 1.0))
#                 st.session_state.user_songs = st.session_state.user_songs[(st.session_state.user_songs['valence'] > val_min) & (st.session_state.user_songs['valence'] < val_max)]
#                 st.write(st.session_state.user_songs)
                
            
#             slider_value = None
#             slider_value = st.slider("On a scale of 1 to 5, how much do you want to dance?", min_value=0, max_value=5, step=1)
#             st.write("You selected:", slider_value)
            
#             if slider_value > 0:
               
            
            

            
     
                
                
           
        
#********************RUNNING APP***********************        
if __name__ == "__main__":
    main()     
        

