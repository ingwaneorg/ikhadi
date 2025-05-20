from flask import Flask, render_template, request, jsonify, redirect, url_for
import random
import string
import time
import os

app = Flask(__name__)

# Check if in development mode
is_development = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1'

# In-memory "database"
poker_sessions = {}

# Helper function to generate session ID
def generate_session_id():
    return ''.join(random.choices(string.digits, k=3))

@app.route('/')
def index():
    return render_template('index.html', dev_mode=is_development)

@app.route('/create', methods=['POST'])
def create_session():
    session_id = generate_session_id()
    
    # Create new session
    poker_sessions[session_id] = {
        "participants": {},
        "current_story": "",
        "revealed": False,
        "last_activity": int(time.time()),
        "rounds": 1
    }
    
    return redirect(url_for('admin_view', session_id=session_id))

@app.route('/<session_id>')
def session_view(session_id):
    if session_id not in poker_sessions:
        return redirect(url_for('index'))
    
    return render_template('session.html', session_id=session_id)

@app.route('/<session_id>/admin')
def admin_view(session_id):
    if session_id not in poker_sessions:
        return redirect(url_for('index'))
    
    return render_template('admin.html', session_id=session_id)

# API endpoints
@app.route('/api/<session_id>/join', methods=['POST'])
def api_join(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    data = request.json
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    
    if not user_id or not user_name:
        return jsonify({"error": "User ID and name required"}), 400
    
    poker_sessions[session_id]["participants"][user_id] = {
        "name": user_name,
        "vote": None,
        "timestamp": int(time.time())
    }
    
    return jsonify({"success": True})

@app.route('/api/<session_id>/vote', methods=['POST'])
def api_vote(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    data = request.json
    user_id = data.get('user_id')
    vote = data.get('vote')
    
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    
    if user_id not in poker_sessions[session_id]["participants"]:
        return jsonify({"error": "User not in session"}), 400
    
    poker_sessions[session_id]["participants"][user_id]["vote"] = vote
    poker_sessions[session_id]["last_activity"] = int(time.time())
    
    return jsonify({"success": True})

@app.route('/api/<session_id>/story', methods=['POST'])
def api_set_story(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    data = request.json
    story = data.get('story')
    
    poker_sessions[session_id]["current_story"] = story
    poker_sessions[session_id]["last_activity"] = int(time.time())
    
    return jsonify({"success": True})

@app.route('/api/<session_id>/reveal', methods=['POST'])
def api_reveal(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    poker_sessions[session_id]["revealed"] = True
    
    return jsonify({"success": True})

@app.route('/api/<session_id>/reset', methods=['POST'])
def api_reset(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    # Reset votes but keep participants
    for user_id in poker_sessions[session_id]["participants"]:
        poker_sessions[session_id]["participants"][user_id]["vote"] = None
    
    poker_sessions[session_id]["revealed"] = False
    poker_sessions[session_id]["rounds"] += 1
    
    return jsonify({"success": True})

@app.route('/api/<session_id>/status', methods=['GET'])
def api_status(session_id):
    if session_id not in poker_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session_data = poker_sessions[session_id]
    
    # Calculate statistics
    votes = [p["vote"] for p in session_data["participants"].values() 
             if p["vote"] is not None and isinstance(p["vote"], (int, float))]
    
    stats = {
        "total_participants": len(session_data["participants"]),
        "votes_submitted": len(votes),
        "mean": sum(votes) / len(votes) if votes else 0,
        "median": sorted(votes)[len(votes)//2] if votes else 0,
        "min": min(votes) if votes else 0,
        "max": max(votes) if votes else 0,
        "round": session_data["rounds"],
        "revealed": session_data["revealed"]
    }
    
    # Count vote frequencies for mode
    if votes:
        vote_counts = {}
        for vote in votes:
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
        stats["mode"] = max(vote_counts, key=vote_counts.get)
        
        # Calculate consensus percentage
        most_common_count = vote_counts[stats["mode"]]
        stats["consensus_percentage"] = (most_common_count / len(votes)) * 100
    
    return jsonify({
        "success": True,
        "current_story": session_data["current_story"],
        "participants": session_data["participants"],
        "revealed": session_data["revealed"],
        "statistics": stats
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
