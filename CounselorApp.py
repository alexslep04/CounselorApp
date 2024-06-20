from flask import Flask, request, jsonify, send_from_directory, send_file
from openai import OpenAI
import os
import fitz  # PyMuPDF
import tempfile

client = OpenAI(api_key='sk-proj-bMRs70IJUB9sPRWYTo5AT3BlbkFJdTJyVq9vvBq00vLsZ1Jo')

app = Flask(__name__)

sessions = {}

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/start_session', methods=['POST'])
def start_session():
    user_id = request.json['user_id']
    sessions[user_id] = {"step": 1, "data": {}, "messages": []}
    return jsonify({"message": "Hello! Please upload your CV/resume if you have one. If not send your name to get started!"})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    user_id = request.form['user_id']
    file = request.files['file']
    session = sessions.get(user_id)
    
    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404
    
    # Save the file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        file.save(temp_file.name)
        temp_file_path = temp_file.name
    
    # Extract text from the PDF
    pdf_text = extract_text_from_pdf(temp_file_path)
    
    # Update session data with PDF text
    session['data']['pdf_context'] = pdf_text
    
    # Extract user's name using ChatGPT
    user_name = extract_name_with_gpt(pdf_text)
    session['data']['name'] = user_name
    
    # Prepare thank you message with user's name
    thank_you_message = f"Nice to meet you, {user_name.strip()}! What are your most important 3 responsibilities at work?"
    
    session['messages'].append({"role": "assistant", "content": thank_you_message})
    session['step'] = 3  # Skip to step 3 since we have the name and resume
    return jsonify({"message": thank_you_message})

@app.route('/export_session', methods=['POST'])
def export_session():
    user_id = request.json['user_id']
    session = sessions.get(user_id)

    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404

    # Create a text file with the session details
    file_path = f"session_{user_id}.txt"
    with open(file_path, 'w') as file:
        file.write("Chat Session\n")
        file.write("=" * 40 + "\n\n")
        for message in session['messages']:
            role = "User" if message['role'] == 'user' else "Assistant"
            file.write(f"{role}: {message['content']}\n\n\n\n")

    return send_file(file_path, as_attachment=True, download_name=f"session_{user_id}.txt")


@app.route('/next_step', methods=['POST'])
def next_step():
    user_id = request.json['user_id']
    user_input = request.json['input']
    session = sessions.get(user_id)

    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404

    step = session['step']
    messages = session['messages']
    messages.append({"role": "user", "content": user_input})

    if step == 1:
        session['data']['name'] = user_input
        next_message = "Nice to meet you " + session['data']['name'] + "! In 25 words or less, how would you describe your current job if someone you didn't know asked you at a party?"
    elif step == 2:
        session['data']['current_job_description'] = user_input
        next_message = "What are your 3 most important responsibilities at work?"
    elif step == 3:
        session['data']['responsibilities'] = user_input
        next_message = "What do you like most about your current job?"
    elif step == 4:
        session['data']['likes'] = user_input
        next_message = "What do you dislike most about your current job? Or, what three changes would you make to your current position that would improve your overall job satisfaction?"
    elif step == 5:
        session['data']['dislikes_or_changes'] = user_input
        next_message = "Please provide a few examples of your interests, hobbies, or unique talents."
    elif step == 6:
        session['data']['interests'] = user_input
        next_message = "Do you have any alternative jobs in mind? Or, what positions have you seen (in job postings, TV, or movies) that you'd like to explore in more detail?"
    elif step == 7:
        session['data']['alternative_jobs'] = user_input
        next_message = "What is more important to you... being in a position that offers the ability to make as much money as possible or is just enjoyable and fun?"
    elif step == 8:
        session['data']['money_or_fun'] = user_input
        next_message = "Given the choice, would you prefer to manage people or just be an individual contributor?"
    elif step == 9:
        session['data']['manage_or_contribute'] = user_input
        next_message = "Is there anything else you'd like me to know about before I suggest some new positions for you (work environment, specific industries, company size, etc.)?"
    elif step == 10:
        session['data']['additional_info'] = user_input
        prompt = generate_prompt(session['data'])
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ]
        )
        session['data']['job_suggestions'] = response.choices[0].message.content.strip()
        next_message = f"Based on your input, here are some job suggestions:\n\n{session['data']['job_suggestions']}\n\n"
        session['step'] = 11
    elif step == 11:
        next_message = "Please select 2-3 jobs for a personalized test."
    else:
        # Continuation of the conversation after the test
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": f"User data: {session['data']}"},
                *messages,
            ]
        )
        next_message = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": next_message})
        session['messages'] = messages

    messages.append({"role": "assistant", "content": next_message})
    session['messages'] = messages
    session['step'] += 1
    return jsonify({"message": next_message})

@app.route('/generate_more_info', methods=['POST'])
def generate_more_info():
    data = request.json
    user_id = data.get('user_id')
    job = data.get('job')
    session = sessions.get(user_id)

    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Provide more information about the job: {job}"},
        ]
    )
    job_info = response.choices[0].message.content.strip()
    
    if 'job_infos' not in session['data']:
        session['data']['job_infos'] = {}
    
    session['data']['job_infos'][job] = job_info
    return jsonify({"info": job_info})

@app.route('/generate_personalized_test', methods=['POST'])
def generate_personalized_test():
    user_id = request.json['user_id']
    jobs = request.json['jobs']
    prompt = request.json['prompt']

    session = sessions.get(user_id)
    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404

    # Create the prompt with selected jobs
    test_prompt = f"The user is looking for a new job. They are interested in the following jobs: {', '.join(jobs)}. {prompt}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": test_prompt},
        ]
    )
    test = response.choices[0].message.content.strip()
    session['data']['personality_test'] = test
    return jsonify({"test": test})

@app.route('/evaluate_test', methods=['POST'])
def evaluate_test():
    user_id = request.json['user_id']
    test_answer = request.json['test_answer']
    test = request.json['test']
    
    session = sessions.get(user_id)
    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404
    
    if 'personality_test_answers' not in session['data']:
        session['data']['personality_test_answers'] = []
    
    session['data']['personality_test_answers'].append(test_answer)
    
    # Check if the user has answered all test questions
    if len(session['data']['personality_test_answers']) < 3:
        next_question = test.split("\n")[len(session['data']['personality_test_answers'])]
        return jsonify({"message": next_question})
    
    # Generate evaluation prompt
    eval_prompt = generate_evaluation_prompt(session['data'])
    eval_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": eval_prompt},
        ]
    )
    best_fit_job = eval_response.choices[0].message.content.strip()
    session['data']['best_fit_job'] = best_fit_job
    
    return jsonify({"message": f"Based on your answers, the best fit job for you is: {best_fit_job}. Thank you for using our service!"})

def extract_text_from_pdf(file_path):
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
    return text

def extract_name_with_gpt(pdf_text):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Only reply with the name do not include anything else"},
            {"role": "user", "content": f"Extract only the user's first and last name from the following resume text:\n\n{pdf_text}"},
        ]
    )
    name = response.choices[0].message.content.strip()
    return name

def generate_prompt(data):
    previous_suggestions = data.get('job_suggestions', 'Not provided')
    pdf_context = data.get('pdf_context', '')
    return f"User data: {data}. Previous job suggestions: {previous_suggestions}. PDF context: {pdf_context}. Suggest 5 new potential job roles."

def generate_personality_test_prompt(data):
    chosen_jobs = data['chosen_jobs']
    job_suggestions = data.get('job_suggestions', 'Not provided')
    pdf_context = data.get('pdf_context', '')
    return (f"The user has chosen the following jobs: {chosen_jobs}. "
            f"Job suggestions provided were: {job_suggestions}. "
            f"PDF context: {pdf_context}. "
            f"Please identify the key differences between these jobs and create a personality test with 3 questions "
            f"to help determine which job is the best fit for the user.")

def generate_evaluation_prompt(data):
    chosen_jobs = data['chosen_jobs']
    answers = data['personality_test_answers']
    job_suggestions = data.get('job_suggestions', 'Not provided')
    job_preferences = data.get('job_preferences', '')
    pdf_context = data.get('pdf_context', '')
    return (f"The user has chosen the following jobs: {chosen_jobs}. "
            f"Job suggestions provided were: {job_suggestions}. "
            f"The user's job preferences are: {job_preferences}. "
            f"Here are their answers to the personality test: {answers}. "
            f"PDF context: {pdf_context}. "
            f"Based on these answers, which job is the best fit for the user and why?")

def ask_personality_test_questions(session):
    questions = session['data']['personality_test'].split("\n")
    question_index = len(session['data']['personality_test_answers'])
    return jsonify({"message": questions[question_index]})

if __name__ == '__main__':
    app.run(debug=True)
