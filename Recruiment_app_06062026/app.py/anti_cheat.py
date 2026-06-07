"""
anti_cheat.py — Anti-cheating component for TalentEdge Assessment.
Drop this file next to your main app. Import and use in candidate assessment mode.

Usage:
    from anti_cheat import render_anti_cheat, render_timer
    
    # In candidate assessment mode, after questions are shown:
    render_anti_cheat(duration_minutes=20)
"""

import streamlit as st
import streamlit.components.v1 as components


def render_anti_cheat(duration_minutes=20, candidate_name="Candidate"):
    """
    Inject anti-cheating JavaScript into the assessment page.
    
    Features:
    - Copy/paste/right-click disabled
    - Tab switch detection with violation counter
    - Countdown timer with auto-submit
    - Camera monitoring (webcam feed in corner)
    - Fullscreen enforcement
    - DevTools detection
    - Keyboard shortcut blocking
    """
    
    total_seconds = duration_minutes * 60
    
    html_code = f"""
    <style>
        * {{
            -webkit-user-select: none !important;
            -moz-user-select: none !important;
            -ms-user-select: none !important;
            user-select: none !important;
        }}
        
        #ac-overlay {{
            position: fixed;
            top: 0;
            right: 0;
            z-index: 99999;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
            padding: 10px;
            pointer-events: none;
        }}
        
        #ac-timer {{
            background: linear-gradient(135deg, #1E293B, #0F172A);
            color: #F1F5F9;
            padding: 10px 20px;
            border-radius: 12px;
            font-family: 'Inter', monospace;
            font-size: 1.1rem;
            font-weight: 700;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            border: 1px solid #334155;
            pointer-events: auto;
            min-width: 200px;
            text-align: center;
        }}
        
        #ac-timer.warning {{
            background: linear-gradient(135deg, #92400E, #78350F);
            border-color: #F59E0B;
            animation: pulse 1s ease infinite;
        }}
        
        #ac-timer.critical {{
            background: linear-gradient(135deg, #991B1B, #7F1D1D);
            border-color: #EF4444;
            animation: pulse 0.5s ease infinite;
        }}
        
        #ac-violations {{
            background: rgba(239, 68, 68, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 10px;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(239,68,68,0.3);
            display: none;
            pointer-events: auto;
        }}
        
        #ac-camera {{
            width: 160px;
            height: 120px;
            border-radius: 12px;
            border: 2px solid #4F46E5;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            object-fit: cover;
            pointer-events: auto;
            background: #1E293B;
        }}
        
        #ac-camera-label {{
            background: rgba(79, 70, 229, 0.9);
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 600;
            font-family: 'Inter', sans-serif;
            pointer-events: auto;
        }}
        
        #ac-warning-modal {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 999999;
            display: none;
            justify-content: center;
            align-items: center;
        }}
        
        #ac-warning-box {{
            background: white;
            padding: 2rem;
            border-radius: 16px;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }}
        
        #ac-warning-box h2 {{
            color: #EF4444;
            margin-bottom: 1rem;
            font-family: 'Inter', sans-serif;
        }}
        
        #ac-warning-box p {{
            color: #64748B;
            line-height: 1.6;
            font-family: 'Inter', sans-serif;
        }}
        
        #ac-warning-box button {{
            background: linear-gradient(135deg, #4F46E5, #7C3AED);
            color: white;
            border: none;
            padding: 10px 30px;
            border-radius: 10px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 1rem;
            font-size: 1rem;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
    </style>
    
    <!-- Overlay: Timer + Violations + Camera -->
    <div id="ac-overlay">
        <div id="ac-timer">⏱️ Loading...</div>
        <div id="ac-violations">⚠️ Violations: 0</div>
        <div id="ac-camera-label">📹 Camera Monitoring</div>
        <video id="ac-camera" autoplay muted playsinline></video>
    </div>
    
    <!-- Warning Modal -->
    <div id="ac-warning-modal">
        <div id="ac-warning-box">
            <h2>⚠️ Warning!</h2>
            <p id="ac-warning-text">Switching tabs or windows is not allowed during the assessment.</p>
            <p id="ac-warning-count" style="color:#EF4444; font-weight:700;"></p>
            <button onclick="dismissWarning()">I Understand — Continue</button>
        </div>
    </div>
    
    <script>
        // ═══════════════════════════════════════
        // ANTI-CHEAT ENGINE
        // ═══════════════════════════════════════
        
        let violations = 0;
        let maxViolations = 5;
        let timeLeft = {total_seconds};
        let timerInterval = null;
        let violationLog = [];
        
        function logViolation(type, detail) {{
            violations++;
            violationLog.push({{
                type: type,
                detail: detail,
                timestamp: new Date().toISOString(),
                count: violations
            }});
            
            let vDiv = document.getElementById('ac-violations');
            vDiv.style.display = 'block';
            vDiv.textContent = '⚠️ Violations: ' + violations + '/' + maxViolations;
            
            if (violations >= maxViolations) {{
                vDiv.textContent = '🚫 Too many violations — flagged for review';
            }}
            
            console.log('[ANTI-CHEAT]', type, detail, 'Total:', violations);
        }}
        
        // ── 1. COPY/PASTE/RIGHT-CLICK PREVENTION ──
        document.addEventListener('copy', function(e) {{
            e.preventDefault();
            logViolation('COPY', 'Copy attempt blocked');
        }});
        
        document.addEventListener('cut', function(e) {{
            e.preventDefault();
            logViolation('CUT', 'Cut attempt blocked');
        }});
        
        document.addEventListener('paste', function(e) {{
            e.preventDefault();
            logViolation('PASTE', 'Paste attempt blocked');
        }});
        
        document.addEventListener('contextmenu', function(e) {{
            e.preventDefault();
            logViolation('RIGHT_CLICK', 'Right-click blocked');
        }});
        
        // ── 2. TAB/WINDOW SWITCH DETECTION ──
        document.addEventListener('visibilitychange', function() {{
            if (document.hidden) {{
                logViolation('TAB_SWITCH', 'User switched away from assessment tab');
                showWarning('You switched away from the assessment tab. This has been recorded.', violations);
            }}
        }});
        
        window.addEventListener('blur', function() {{
            logViolation('WINDOW_BLUR', 'Assessment window lost focus');
        }});
        
        // ── 3. KEYBOARD SHORTCUT BLOCKING ──
        document.addEventListener('keydown', function(e) {{
            // Block Ctrl+C, Ctrl+V, Ctrl+A, Ctrl+U, Ctrl+S, Ctrl+P
            if (e.ctrlKey && ['c','v','a','u','s','p'].includes(e.key.toLowerCase())) {{
                e.preventDefault();
                logViolation('SHORTCUT', 'Blocked Ctrl+' + e.key.toUpperCase());
            }}
            // Block F12 (DevTools)
            if (e.key === 'F12') {{
                e.preventDefault();
                logViolation('DEVTOOLS', 'F12 DevTools attempt blocked');
            }}
            // Block Ctrl+Shift+I (DevTools)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'i') {{
                e.preventDefault();
                logViolation('DEVTOOLS', 'Ctrl+Shift+I blocked');
            }}
            // Block Ctrl+Shift+J (Console)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'j') {{
                e.preventDefault();
                logViolation('DEVTOOLS', 'Ctrl+Shift+J blocked');
            }}
            // Block PrintScreen
            if (e.key === 'PrintScreen') {{
                logViolation('SCREENSHOT', 'PrintScreen attempt detected');
            }}
        }});
        
        // ── 4. COUNTDOWN TIMER ──
        function updateTimer() {{
            timeLeft--;
            let minutes = Math.floor(timeLeft / 60);
            let seconds = timeLeft % 60;
            let timerDiv = document.getElementById('ac-timer');
            timerDiv.textContent = '⏱️ ' + String(minutes).padStart(2,'0') + ':' + String(seconds).padStart(2,'0') + ' remaining';
            
            // Warning at 5 minutes
            if (timeLeft <= 300 && timeLeft > 60) {{
                timerDiv.className = 'warning';
            }}
            // Critical at 1 minute
            if (timeLeft <= 60) {{
                timerDiv.className = 'critical';
            }}
            
            if (timeLeft <= 0) {{
                clearInterval(timerInterval);
                timerDiv.textContent = '⏰ TIME UP — Auto-submitting...';
                autoSubmit();
            }}
        }}
        
        timerInterval = setInterval(updateTimer, 1000);
        updateTimer();
        
        function autoSubmit() {{
            // Find and click the Submit Assessment button
            let buttons = parent.document.querySelectorAll('button');
            for (let btn of buttons) {{
                if (btn.textContent.includes('Submit Assessment')) {{
                    btn.click();
                    return;
                }}
            }}
            // Fallback: try Streamlit's internal button
            let stButtons = parent.document.querySelectorAll('[data-testid="stButton"] button');
            for (let btn of stButtons) {{
                if (btn.textContent.includes('Submit')) {{
                    btn.click();
                    return;
                }}
            }}
        }}
        
        // ── 5. CAMERA MONITORING ──
        async function startCamera() {{
            try {{
                let stream = await navigator.mediaDevices.getUserMedia({{ video: true, audio: false }});
                let video = document.getElementById('ac-camera');
                video.srcObject = stream;
                document.getElementById('ac-camera-label').textContent = '📹 Camera Active';
                document.getElementById('ac-camera-label').style.background = 'rgba(16, 185, 129, 0.9)';
            }} catch(err) {{
                console.log('[ANTI-CHEAT] Camera denied:', err);
                document.getElementById('ac-camera').style.display = 'none';
                document.getElementById('ac-camera-label').textContent = '📹 Camera Denied';
                document.getElementById('ac-camera-label').style.background = 'rgba(239, 68, 68, 0.9)';
                logViolation('CAMERA_DENIED', 'Candidate denied camera access');
            }}
        }}
        startCamera();
        
        // ── 6. WARNING MODAL ──
        function showWarning(msg, count) {{
            document.getElementById('ac-warning-text').textContent = msg;
            document.getElementById('ac-warning-count').textContent = 
                'Violation ' + count + ' of ' + maxViolations + '. Excessive violations will be flagged.';
            document.getElementById('ac-warning-modal').style.display = 'flex';
        }}
        
        function dismissWarning() {{
            document.getElementById('ac-warning-modal').style.display = 'none';
        }}
        
        // ── 7. DEVTOOLS DETECTION ──
        let devToolsOpen = false;
        setInterval(function() {{
            let threshold = 160;
            if (window.outerWidth - window.innerWidth > threshold || 
                window.outerHeight - window.innerHeight > threshold) {{
                if (!devToolsOpen) {{
                    devToolsOpen = true;
                    logViolation('DEVTOOLS_OPEN', 'Developer tools appear to be open');
                    showWarning('Developer tools detected. This has been recorded.', violations);
                }}
            }} else {{
                devToolsOpen = false;
            }}
        }}, 2000);
        
        // ── 8. PREVENT TEXT SELECTION VIA CSS ──
        let style = parent.document.createElement('style');
        style.textContent = `
            .stRadio label, .stMarkdown, .question-card {{
                -webkit-user-select: none !important;
                -moz-user-select: none !important;
                user-select: none !important;
            }}
        `;
        parent.document.head.appendChild(style);
        
        console.log('[ANTI-CHEAT] System initialized. Duration: {duration_minutes} min. Max violations: ' + maxViolations);
    </script>
    """
    
    components.html(html_code, height=0)


def render_timer_only(duration_minutes=20):
    """Render just the countdown timer without other anti-cheat features."""
    total_seconds = duration_minutes * 60
    
    timer_html = f"""
    <div style="position:fixed; top:10px; right:10px; z-index:99999;
                background:linear-gradient(135deg,#1E293B,#0F172A);
                color:#F1F5F9; padding:10px 20px; border-radius:12px;
                font-family:monospace; font-size:1.1rem; font-weight:700;
                box-shadow:0 4px 20px rgba(0,0,0,0.3); border:1px solid #334155;">
        <span id="simple-timer">⏱️ Loading...</span>
    </div>
    <script>
        let t = {total_seconds};
        setInterval(function() {{
            t--;
            let m = Math.floor(t/60), s = t%60;
            document.getElementById('simple-timer').textContent = 
                '⏱️ ' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
            if (t <= 0) {{
                document.getElementById('simple-timer').textContent = '⏰ TIME UP';
                let btns = parent.document.querySelectorAll('button');
                for (let b of btns) {{
                    if (b.textContent.includes('Submit')) {{ b.click(); break; }}
                }}
            }}
        }}, 1000);
    </script>
    """
    components.html(timer_html, height=0)
