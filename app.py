from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>Iyer's Math Center (IMC) - Live Classroom is Ready!</h1>
    <p>Teacher Sreekala - This link will work in your MY CLASSROOM app.</p>
    <p>Status: HTTPS Ready ✅</p>
    """

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
