from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import uuid
import re
import os
import json
from datetime import datetime

# Get the version number
from version import __version__

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-for-development')

# Limit the number of rooms and number of active learners per room
MAX_ROOMS = 10
MAX_LEARNERS_PER_ROOM = 20
ALLOWED_ESTIMATES = {'0', '0.5', '1', '2', '3', '5', '8', '13', '20'}

# In-memory storage
rooms = {}

def validate_room_code(room_code):
    """Validate room code: only letters, numbers, hyphens, 2-10 characters"""
    return bool(re.match(r'^[A-Za-z0-9-]{2,10}$', room_code))

def get_status_symbol(status):
    """Convert status to HTML icon representation"""
    if not status:
        return '&nbsp;'
    
    status_map = {
        'hand-up' : '<i class="far fa-hand-paper hand-up"></i>',
        'not-sure': '<i class="fas fa-question-circle not-sure"></i>',
        'break'   : '<i class="fas fa-mug-hot break"></i>',
    }
    
    return status_map.get(status, f'<b>{status}</b>')

def clear_estimates(room_code):
    """Clear all estimates for a given room code"""

    if not validate_room_code(room_code):
        return False
        
    for learner in rooms[room_code]['learners'].values():
        # Update lastCommunication for any interaction
        learner['status'] = ''
        learner['lastCommunication'] = datetime.now().isoformat() + 'Z'

    return True

@app.route('/')
def intro():
    return render_template('intro.html')

@app.route('/join', methods=['POST'])
def join_room():
    room_code = request.form.get('room_code', '').lower().strip()
    role = request.form.get('role')  # 'learner' or 'tutor'
    
    if not room_code or not validate_room_code(room_code):
        return redirect(url_for('intro'))
    
    if role == 'tutor':
        return redirect(url_for('poker_page', room_code=room_code))
    else:
        return redirect(url_for('learner_page', room_code=room_code))

def get_learner_id():
    if 'learner_id' not in session:
        # Generate a unique code for each user
        learner_uuid = str(uuid.uuid4())
        session['learner_id'] = learner_uuid

    return session['learner_id']

@app.route('/<room_code>')
def learner_page(room_code):
    # Block any query parameters for security
    if request.args:
        return "Forbidden", 403
    
    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()
    
    # Show an 404 error if tutor hasn't created the room
    if room_code not in rooms:
        return "Room not found", 404

    # Limit how many active learners can be in a room
    room = rooms[room_code]      
    active_learners = [l for l in room['learners'].values() if l.get('isActive')]
    if len(active_learners) >= MAX_LEARNERS_PER_ROOM:
        return "Room is full", 403  # or 429 Too Many Requests

    learner_id = get_learner_id()
    
    # Find existing learner or create new one
    if learner_id not in rooms[room_code]['learners']:
        rooms[room_code]['learners'][learner_id] = {
            'name': '',
            'isActive': True,
            'lastCommunication': datetime.now().isoformat() + 'Z',
            # These fields get added when learner interacts
            'status': '',
        }
    
    learner = rooms[room_code]['learners'][learner_id]
    
    return render_template('learner.html', 
                         room=rooms[room_code], 
                         learner=learner,
                         learner_id=learner_id)

# Save the database if in DEBUG mode
def save_db_json():
    if app.debug:
        with open('db.json', 'w') as f:
            json.dump(rooms, f, indent=2, default=str)

@app.route('/<room_code>/update', methods=['POST'])
def update_learner(room_code):
    room_code = room_code.lower()
    learner_id = get_learner_id()
    
    if not validate_room_code(room_code):
        return jsonify({'success': False, 'error': 'Invalid room code'})
    
    if not learner_id or room_code not in rooms:
        return jsonify({'success': False, 'error': 'Invalid session or room'})
    
    if learner_id not in rooms[room_code]['learners']:
        rooms[room_code]['learners'][learner_id] = {
            'name': '',  # starts empty
            'isActive': True,
        }

    data = request.get_json()
    learner = rooms[room_code]['learners'][learner_id]
    
    # Update lastCommunication for any interaction
    learner['isActive'] = True
    learner['lastCommunication'] = datetime.now().isoformat() + 'Z'
    
    # Update learner data
    if 'name' in data:
        learner['name'] = data['name'][:15]  # Max 15 characters
    
    if 'status' in data:
        learner['status'] = data['status']
        
    save_db_json()
    return jsonify({'success': True, 'timestamp': datetime.now().isoformat()})

@app.route('/<room_code>/poker')
def poker_page(room_code):
    """Show estimates for a room and the stats for the esimates"""
    show_param = request.args.get('show', 'false').lower()

    if not validate_room_code(room_code):
        return "Invalid room code", 400
        
    room_code = room_code.lower()

    # Initialize room if it doesn't exist
    if room_code not in rooms:
        # Limit number of rooms
        if len(rooms) >= MAX_ROOMS:
            return "Maximum number of rooms reached", 403

        rooms[room_code] = {
            'code': room_code,
            'description': f'Room {room_code.upper()}',
            'learners': {},  # Dictionary, not array
            'createdDate': datetime.now().isoformat() + 'Z'
        }

    # See if the user wants the estimates cleared
    if show_param == 'clear':
        clear_estimates(room_code)
        show_values = False
    else:
        show_values = (show_param == 'true')    

    # Get poker values (numeric responses)
    poker_values = []
    total_learners = len(rooms[room_code]['learners'])

    # Count active learners
    total_learners = sum(
        1 for learner in rooms[room_code]['learners'].values()
        if learner.get('isActive')
    )
    
    for learner in rooms[room_code]['learners'].values():
        # Skip inactive learners
        if not learner.get('isActive'):
            continue
        
        # Only use numeric statuses
        status = learner.get('status', '')
        if status in ALLOWED_ESTIMATES:
            poker_values.append(float(status))
   
    # Calculate statistics
    avg_text = 'no average'
    stats = {}
    consensus = 0
    consensus_votes = 0
    
    if poker_values:
        min_val = min(poker_values)
        max_val = max(poker_values)

        stats['min'] = int(min_val) if min_val % 1 == 0 else min_val
        stats['max'] = int(max_val) if max_val % 1 == 0 else max_val
        stats['count'] = len(poker_values)
        stats['average'] = round(sum(poker_values)/len(poker_values),1)
        stats['values'] = sorted(poker_values)
        
        # Show the average calculation
        avg_text = f"avg = {sum(poker_values)} ÷ {len(poker_values)}"
    
        # Calculate consensus (most common value percentage)
        if poker_values:
            most_common_count = max(poker_values.count(x) for x in set(poker_values))
            consensus = round((most_common_count / len(poker_values)) * 100)
            consensus_votes = most_common_count
            # if common count is 1 then NO consensus
            if most_common_count == 1:
                consensus = 0
                consensus_votes = 0

    # Get learner estimates
    learner_estimates = []
    for learner in rooms[room_code]['learners'].values():
        if not learner.get('isActive'):
            continue

        name = learner.get('name', 'Unknown')
        status = learner.get('status', '').strip()

        if status in ALLOWED_ESTIMATES:
            estimate = float(status)
            if estimate.is_integer():
                estimate = int(estimate)
        else:
            if status in ('hand-up','not-sure','break'):
                estimate = status
            else:
                estimate = ''

        learner_estimates.append({
            "name": name,
            "estimate": estimate,
        })

    # Add mock data for testing
    if app.debug:
            learner_estimates.append({"name": "Mblank"  ,"estimate": ""})
            learner_estimates.append({"name": "Mhandup" ,"estimate": "hand-up"})
            learner_estimates.append({"name": "Mnotsure","estimate": "not-sure"})
            learner_estimates.append({"name": "Mbreak"  ,"estimate": "break"})
            #learner_estimates.append({"name": "Mother" ,"estimate": "other"})
            for i in range(3):
                estimate = list(ALLOWED_ESTIMATES)[i]
                learner_estimates.append({"name": f"Mock{i+1}","estimate": estimate})

    return render_template('poker.html', 
            room=rooms[room_code], 
            stats=stats,
            total_learners=total_learners,
            consensus=consensus,
            consensus_votes=consensus_votes,
            learner_estimates=learner_estimates,
            show_values=show_values,
            average_text=avg_text,
            )

@app.route('/api')
def block_api_root():
    return 'Access to /api is not allowed', 403

@app.route('/api/rooms')
def api_rooms():
    return jsonify(rooms)

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'rooms'  : f'{len(rooms)}/{MAX_ROOMS}',
        'service': 'ikhadi',
        'size db': len(json.dumps(rooms).encode("utf-8")),
        'status' : 'healthy',
        'version': __version__,
    })

@app.context_processor
def utility_processor():
    return dict(get_status_symbol=get_status_symbol)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
