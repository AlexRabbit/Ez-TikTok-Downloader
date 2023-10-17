import requests
import os
import re
from datetime import datetime
import time

def download_video(tiktok_url):
    # Define the third-party API endpoint
    api_endpoint = 'https://www.tikwm.com/api/'

    # Create the request parameters
    params = {
        'url': tiktok_url,
        'hd': 1  # Set to 1 to get HD Video (optional)
    }

    # Make a GET request to the third-party API
    response = requests.get(api_endpoint, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        response_data = response.json()
        if response_data['code'] == 0:
            # Extract the username from the TikTok URL
            username = re.search(r'@(\w+)', tiktok_url).group(1)

            # Extract the video ID
            video_id = re.search(r'/video/(\d+)', tiktok_url).group(1)

            # Extract the date of publishing
            date_of_publish = datetime.now().strftime('%Y%m%d')

            # Create a folder with the username if it doesn't exist
            if not os.path.exists(username):
                os.makedirs(username)

            # Generate a filename for the video
            filename = os.path.join(username, f"{username}_{video_id}.mp4")

            # Check if the file already exists
            if not os.path.exists(filename):
                # Download the video and save it inside the folder
                video_url_without_watermark = response_data['data']['play']
                video_data = requests.get(video_url_without_watermark).content
                with open(filename, 'wb') as video_file:
                    video_file.write(video_data)

                print(f"Video downloaded and saved as: {filename}")
            else:
                print(f"Video already exists: {filename}")
        else:
            print(f"Error: {response_data['msg']}")
    else:
        print("Error: Unable to obtain the video URL without watermark")

def main():
    user_input = input("Enter a TikTok video URL or a path to a .txt file with a list of URLs: ")
    
    if user_input.endswith(".txt"):
        # If the input ends with ".txt," treat it as a file path and process URLs from the file
        if os.path.isfile(user_input):
            with open(user_input, 'r') as file:
                for line in file:
                    tiktok_url = line.strip()
                    download_video(tiktok_url)
                    time.sleep(1)  # Add a one-second delay
        else:
            print("Error: The provided file path does not exist.")
    else:
        # If the input doesn't end with ".txt," assume it's a single URL and download the video
        download_video(user_input)

if __name__ == '__main__':
    main()
