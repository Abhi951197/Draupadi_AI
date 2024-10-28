from flask import Flask, render_template, request, jsonify
from langchain_ollama import ChatOllama

app = Flask(__name__)

# Initialize the ChatOllama model
model = ChatOllama(model="llama3.2:3b", base_url="http://localhost:11434/")

@app.route("/")
def home():
    return render_template("chatbot.html")

@app.route("/generate_response", methods=["POST"])
def generate_response():
    input_text = request.json.get("input_text")
    print(input_text)
    response = model.invoke(input_text)
    print(response)
    return jsonify({"response": response.content})

if __name__ == "__main__":
    app.run(debug=True)