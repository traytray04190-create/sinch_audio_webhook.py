#!/usr/bin/env python3
"""
Sinch Audio Webhook Server - Railway Ready Version
Fixed to use correct SVAML format for Sinch Voice API.

This server handles Sinch webhooks for audio file playback.
When a call is answered (ACE event), it returns SVAML to play audio and hangup.
Deploy this to Railway to get a permanent public URL.
"""

from flask import Flask, request, jsonify
import os
import logging

# Configure logging for Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Audio file URL - can be set via environment variable or query parameter
# Default: empty (will use query parameter from callbackUrlParameters)
AUDIO_URL = os.environ.get('AUDIO_URL', '')

# TTS settings (if using TTS instead of audio file)
USE_TTS = os.environ.get('USE_TTS', 'false').lower() in ('true', '1', 'yes')
TTS_TEXT = os.environ.get('TTS_TEXT', 'Hello, this is an automated message.')


@app.route('/', methods=['GET'])
def health():
    """Health check endpoint for Railway - returns exact JSON format"""
    logger.info("Health check requested")
    return jsonify({
        'status': 'online',
        'service': 'Sinch Audio Webhook',
        'endpoint': '/voice'
    }), 200


@app.route('/voice', methods=['POST'])
def voice():
    """
    Handle incoming Sinch webhook POST request.
    Sinch sends events like 'ice' (Incoming Call Event) and 'ace' (Answered Call Event).
    We respond with SVAML (Sinch Voice API Markup Language) format.
    """
    try:
        # Get JSON data from Sinch
        data = request.get_json() or {}
        
        # Log incoming request for debugging
        logger.info(f"Incoming webhook request: {request.method} {request.path}")
        logger.info(f"Request data: {data}")
        
        # Extract event type
        event = data.get('event', '')
        logger.info(f"Event type: {event}")
        
        # Handle Incoming Call Event (ICE)
        if event == 'ice':
            # When call arrives, answer it first
            # Then Sinch will send 'ace' event when answered
            svaml_response = {
                "action": {
                    "name": "answer"
                }
            }
            logger.info(f"Responding to ICE with: {svaml_response}")
            return jsonify(svaml_response), 200
        
        # Handle Answered Call Event (ACE) - this is when we play audio
        elif event == 'ace':
            # Get audio URL from query parameters (passed via callbackUrlParameters in API call)
            # or from request body, or use environment variable/default
            audio_url = (
                request.args.get('audio_url') or 
                data.get('audio_url') or 
                AUDIO_URL
            )
            
            # If no audio URL and not using TTS, return error
            if not audio_url and not USE_TTS:
                logger.error("No audio URL provided and TTS is disabled")
                return jsonify({
                    'error': 'No audio URL provided. Set audio_url query parameter, request body, or AUDIO_URL environment variable.'
                }), 400
            
            # Build SVAML response with instructions
            instructions = []
            
            if USE_TTS:
                # Use TTS instead of audio file
                instructions.append({
                    "name": "say",
                    "text": TTS_TEXT,
                    "locale": "en-US"
                })
                logger.info(f"Using TTS with text: {TTS_TEXT}")
            else:
                # Use audio file - correct Sinch SVAML format
                instructions.append({
                    "name": "playFiles",
                    "files": [audio_url]
                })
                logger.info(f"Using audio file: {audio_url}")
            
            # SVAML response format for Sinch
            svaml_response = {
                "instructions": instructions,
                "action": {
                    "name": "hangup"
                }
            }
            
            logger.info(f"Responding to ACE with SVAML: {svaml_response}")
            return jsonify(svaml_response), 200
        
        # Handle Disconnect Call Event (DICE) or other events
        elif event == 'dice':
            logger.info("Call disconnected")
            return '', 200
        
        # For any other events, acknowledge with empty response
        else:
            logger.info(f"Unhandled event type: {event}, returning 200 OK")
            return '', 200
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/preview', methods=['GET'])
def preview():
    """
    Preview endpoint to test audio file URL
    Returns JSON with audio URL info for testing
    """
    audio_url = request.args.get('audio_url', AUDIO_URL)
    return jsonify({
        'audio_url': audio_url,
        'status': 'preview',
        'instructions': [{
            "name": "playFiles",
            "files": [audio_url]
        }]
    }), 200


@app.route('/set_audio_url', methods=['POST'])
def set_audio_url():
    """Update the audio file URL (if needed)"""
    global AUDIO_URL
    try:
        data = request.get_json() or {}
        AUDIO_URL = data.get('audio_url', AUDIO_URL)
        logger.info(f"Audio URL updated to: {AUDIO_URL}")
        return jsonify({'status': 'success', 'audio_url': AUDIO_URL}), 200
    except Exception as e:
        logger.error(f"Error setting audio URL: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400


if __name__ == '__main__':
    # Get port from Railway environment variable (they provide this automatically)
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"Starting Sinch Audio Webhook Server on port {port}...")
    logger.info(f"Webhook endpoint: /voice")
    logger.info(f"Health check: /")
    logger.info(f"Default audio URL: {AUDIO_URL or 'Not set (will use query parameter)'}")
    logger.info(f"Using TTS: {USE_TTS}")
    
    # Railway expects the server to listen on 0.0.0.0 (all interfaces)
    # This is critical - if you use '127.0.0.1' or 'localhost', Railway won't be able to reach it
    app.run(host='0.0.0.0', port=port, debug=False)
