from flask import Flask, request, jsonify, send_from_directory
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
    return jsonify({"message": "Session started. What is your name?"})

@app.route('/next_step', methods=['POST'])
def next_step():
    user_id = request.json['user_id']
    user_input = request.json['input']
    session = sessions.get(user_id)

    if not session:
        return jsonify({"message": "Session not found. Please start a new session."}), 404

    step = session['step']
    if step == 1:
        session['data']['name'] = user_input
        next_message = "Please provide your current job description."
    elif step == 2:
        session['data']['current_job'] = user_input
        next_message = "What do you like about your current job?"
    elif step == 3:
        session['data']['likes'] = user_input
        next_message = "What do you dislike about your current job?"
    elif step == 4:
        session['data']['dislikes'] = user_input
        next_message = "Please provide a few examples of your passions."
    elif step == 5:
        session['data']['passions'] = user_input
        next_message = "Do you have any alternative jobs in mind?"
    elif step == 6:
        session['data']['alternative_jobs'] = user_input
        next_message = "Is there anything else you would like to let me know before I suggest any jobs?"
    elif step == 7:
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
        next_message = f"Based on your input, here are some job suggestions:\n\n{session['data']['job_suggestions']}\n\nPlease select 2-3 jobs for a personalized test."
        session['step'] = 8
    elif step == 8:
        next_message = "Please select 2-3 jobs for a personalized test."
    else:
        # Continuation of the conversation after the test
        messages = session['messages']
        messages.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"User data: {session['data']}"},
                *messages,
            ]
        )
        next_message = response.choices[0].message.content.strip()
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
    if 'pdf_context' not in session['data']:
        session['data']['pdf_context'] = []
    session['data']['pdf_context'].append(pdf_text)
    
    # Do not call the API here, just add the context
    session['messages'].append({"role": "user", "content": "PDF uploaded successfully and added to context."})
    
    return jsonify({"message": "PDF uploaded successfully and added to context."})

def extract_text_from_pdf(file_path):
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
    return text

def generate_prompt(data):
    previous_suggestions = data.get('job_suggestions', 'Not provided')
    pdf_context = "\n\n".join(data.get('pdf_context', ''))
    return f"User data: {data}. Previous job suggestions: {previous_suggestions}. PDF context: {pdf_context}. Suggest 5 new potential job roles."

def generate_personality_test_prompt(data):
    chosen_jobs = data['chosen_jobs']
    job_suggestions = data.get('job_suggestions', 'Not provided')
    pdf_context = "\n\n".join(data.get('pdf_context', ''))
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
    pdf_context = "\n\n".join(data.get('pdf_context', ''))
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
