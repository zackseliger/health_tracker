from app import create_app
import os

# Explicitly set environment
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == "__main__":
    app.run(debug=True) 