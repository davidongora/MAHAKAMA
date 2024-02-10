from flask import Flask, jsonify, request, make_response
from flask_session import Session
import openai
import firebase_admin
from firebase_admin import storage, credentials, db, firestore
from dotenv import dotenv_values
# from flask_cors import CORS
import requests
import textwrap

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
# CORS(app)

env_vars = dotenv_values('./env')

openai.api_key = env_vars.get('key')

# Initialize Firebase
cred = credentials.Certificate("./chatbot-1b12b-firebase-adminsdk-xmzh4-b4f9bd484e.json")  # Add your Firebase credentials
firebase_admin.initialize_app(cred, {
    'storageBucket': 'gs://chatbot-1b12b.appspot.com'
})
bucket = storage.bucket("chatbot-1b12b.appspot.com")
db = firestore.client()

def download_document(document_name):
    blob = bucket.blob(document_name)
    # Download the file from Firebase
    file_contents = blob.download_as_string()
    print(file_contents)

    encodings_to_try = ['utf-8', 'latin-1', 'utf-16', 'windows-1252']  # Add more encodings as needed

    for encoding in encodings_to_try:
        try:
            # Try decoding the file contents using the current encoding
            return file_contents.decode(encoding) if file_contents else None
        except UnicodeDecodeError:
            # If decoding fails with this encoding, try the next one
            continue

    # If all encodings fail, return None or handle the error accordingly
    return None  # or raise an exception, log an error, etc.


@app.route('/', methods=['GET'])
def proof_of_life():
    return "i am alive "
@app.route('/answerquestions', methods=['POST'])
def answer_document_questions():
    user_input = request.form['user_input']
    document_name = request.form['document_name']  # Assuming this is the name of the file in Firebase Storage

    # Download document content from Firebase Storage
    document_content = download_document(document_name)

    # chunk the document content into smaller pieces
    chunks = textwrap.wrap(document_content, 1024)

    chatbot_response = ""  # Placeholder response
    
    for chunk in chunks:
        prompt = f"Document: {chunk}\nUser: {user_input}\nChatbot:"
        # Use OpenAI API to generate chatbot response
        response_from_openai = openai.Completion.create(
            engine="davinci",
            prompt=prompt,
            max_tokens=64,
            temperature=0.7,
        )

        # Update the chatbot response in the 'response' dictionary
        chatbot_response += response_from_openai['choices'][0]['text'].strip()

    
    # Generate the complete response including user input, chatbot response, and image URL
    response = {
        "user_input": user_input,
        "chatbot_response": chatbot_response,
        "image_url": "/img/chat.png"  # Adjust this to the actual image URL
    }

    doc_ref = db.collection('user_interactions').document()
    doc_ref.set({
        'user_id': session['user_id'],
        'user_input': user_input,
        'chatbot_response': chatbot_response,
    })


    # what is the use of the function below, the above  code seems to be doing it already?
    if document_content:
        prompt = f"Document: {document_content}\nUser: {user_input}\nChatbot:"
        # Use OpenAI API to generate chatbot response
        response_from_openai = openai.Completion.create(
            engine="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=4032,
            temperature=0.7,
        )

        # Update the chatbot response in the 'response' dictionary
        response["chatbot_response"] = response_from_openai['choices'][0]['text'].strip()

    return jsonify(response), 200

    
    
#     # topic.py

@app.route('/combined_learning/<topic>', methods=['POST', 'OPTIONS'])
def combined_learning(topic):
    if request.method == 'OPTIONS':
        # Handle CORS preflight request
        response = make_response()
        # response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    try:
        # Get the learning program from OpenAI
        learning_program = create_learning_program(topic)

        # Get content from Wikipedia
        content_response = requests.get(
            f"https://en.wikipedia.org/w/api.php?action=query&format=json&titles={topic}&prop=extracts&exintro=1"
        )
        content_response.raise_for_status()  # Raise an exception for HTTP errors
        content = content_response.json().get('query', {}).get('pages', {}).get(next(iter(content_response.json().get('query', {}).get('pages', {}))), {}).get('extract')

        # Return a combined response
        return jsonify({
            "learning_program": learning_program,
            "wikipedia_content": content
        }), 200

    except Exception as e:
        return jsonify({"error": f"Error retrieving combined response: {e}"}), 500

@app.route('/learning/<topic>', methods=['POST']) #endpoint is working
def create_learning_program(topic):
    prompt = f"Create a personalized learning program on {topic}. Include sections on introduction, key concepts, examples, practice exercises, and conclusion."
    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=4032,
        temperature=0.7,
    )
    learning_program = response['choices'][0]['text'].strip()
    # learning_program = "This is a sample learning program."

    return learning_program


@app.route('/learningprogram', methods=['GET'])
def get_learning_program(topic=None):
    if not topic:
        topic = request.args.get('topic')
    
    if not topic:
        return jsonify({"error": "Topic not provided"}), 400
    
    learning_program = create_learning_program(topic)
    
    return jsonify({"learning_program": learning_program}), 200


@app.route('/getcontent/<topic>', methods=["POST"])
def get_content(topic):
    try:
        wikipedia_api_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&titles={topic}&prop=extracts&exintro=1"
        response = requests.get(wikipedia_api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()

        if "query" in data and "pages" in data["query"]:
            page = next(iter(data["query"]["pages"].values()))
            if "extract" in page:
                content = page["extract"]
                return jsonify({"content": content}), 200

        return jsonify({"message": "No content found for the given topic"}), 404

    except requests.exceptions.RequestException as req_error:
        return jsonify({"error": f"Error making Wikipedia API request: {req_error}"}), 500

    except Exception as e:
        return jsonify({"error": f"Error fetching content from Wikipedia: {e}"}), 500
    
@app.route("/alt/content/<topic>", methods=["GET"])
def fetch_alternative_content_1(topic):
    try:
        # Use the Wikipedia API to fetch information about the topic
        wikipedia_api_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&titles={topic}&prop=extracts&exintro=1"
        response = requests.get(wikipedia_api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()

        # Check if the API response contains an 'extract' field
        if "query" in data and "pages" in data["query"]:
            page = next(iter(data["query"]["pages"].values()))
            if "extract" in page:
                content = page["extract"]
                return content

    except requests.exceptions.RequestException as req_error:
        print(f"Error making API request for alternative content 1: {req_error}")
    except Exception as e:
        print(f"Error fetching alternative content 1: {e}")
    return None


# # file.py

# Initialize Firebase app
try:
    # Try to get the default app, which will throw an exception if it doesn't exist
    default_app = firebase_admin.initialize_app()
except ValueError:
    # If the default app already exists, do nothing
    pass

# If the default app doesn't exist, initialize it
if not firebase_admin._apps:
    cred = credentials.Certificate("./chatbot-1b12b-firebase-adminsdk-xmzh4-b4f9bd484e.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'gs://chatbot-1b12b.appspot.com'
    })

@app.route('/dropFiles', methods=['POST'])
def store_file():
    try:
        # Check if the file is in the request
        if 'file' not in request.files:
            return jsonify({"message": "No file provided."}), 400

        uploaded_file = request.files['file']

        if uploaded_file.filename == '':
            return jsonify({"message": "No selected file."}), 400

        # Upload the file to the Google Cloud Storage bucket
        blob = bucket.blob(uploaded_file.filename)
        blob.upload_from_file(uploaded_file.stream)

        return jsonify({"message": "File stored successfully!"}), 200

    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

# endpoint for getting the file stored in the storage.bucket
@app.route('/listFiles', methods=['GET'])
def list_files():
    bucket = storage.bucket('chatbot-1b12b.appspot.com')  # Access the default storage bucket
    blobs = bucket.list_blobs()  # Retrieve a list of blobs (files) in the bucket

    file_list = [blob.name for blob in blobs]  # Extracting file names from the blobs

    return jsonify({"files": file_list}), 200

# Endpoint to save user input and response to Firebase
@app.route('/saveUserInteraction', methods=['POST'])
def save_user_interaction():
    data = request.json
    user_input = data.get('user_input')
    chatbot_response = data.get('chatbot_response')
    
    # Save the user interaction to Firebase
    doc_ref = db.collection('user_interactions').document()
    doc_ref.set({
        'user_id': session['user_id'],
        'user_input': user_input,
        'chatbot_response': chatbot_response,
        # Add more fields as needed
    })
    
    return jsonify({"message": "User interaction saved successfully!"}), 200

if __name__ == '__main__':
    app.run()
    # app.run(debug=True)


# endpoint for saving user inputs and outputs
#registration 
#saving history and display them in cards
#endpoint for sample questions that can be generated from the document select