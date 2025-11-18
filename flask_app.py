import os
import time
import fcntl  # For Unix-based systems
from flask import Flask, request, render_template_string
from exchange_token import register_athlete
from process_data import gen_report, LEADERBOARD_CSV, DAILY_KM_CSV, INVALID_ACTIVITIES_CSV
import io
import zipfile
from flask import send_file, abort
app = Flask(__name__)

# https://www.strava.com/oauth/authorize?client_id=184098&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read,activity:read,activity:read_all

CLIENT_ID = 184098
REDIRECT_URI = "https://tiennt.pythonanywhere.com"
# Basic landing page to show the Strava link
@app.route('/')
def index():
    code = request.args.get('code')
    scope = request.args.get('scope')

    if code:
        try:
            athlete_info = register_athlete(code)
            return f"<h1>Success!</h1><p> Thanks {athlete_info["firstname"]} {athlete_info["lastname"]} for register </p>"
        except Exception as e:
            return f"<h1>Error!</h1><p>Failed to register athlete: {str(e)}</p>"
    scope = "read,activity:read_all"
    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={scope}"
    )

    html = f"""
    <h1>Larion Strava OAuth</h1>
    <a href="{auth_url}">Authorize on Strava</a>
    """
    return html

@app.route('/reports')
def reports():
    gen_report()
    # Replace these with the actual three file paths you want zipped
    file_paths = [
        LEADERBOARD_CSV,
        DAILY_KM_CSV,
        INVALID_ACTIVITIES_CSV
    ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            if not os.path.isfile(fp):
                return abort(404, description=f"File not found: {fp}")
            zf.write(fp, arcname=os.path.basename(fp))
    buf.seek(0)
    # Flask >=2.0 uses download_name; older versions use attachment_filename
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="reports.zip")

if __name__ == '__main__':
    app.run(debug=True)
