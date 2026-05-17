from flask_socketio import SocketIO

# socketio is defined here so both app.py and route files
# can import it without creating a circular import.
# app.py calls socketio.init_app(app) to bind it to the Flask app.
# async_mode='threading' uses Python's built-in threading instead
# of eventlet — simpler and works fine for development.
socketio = SocketIO(async_mode='threading')