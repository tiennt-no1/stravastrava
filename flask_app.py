import os
import time
import fcntl  # For Unix-based systems
from flask import Flask, request, render_template_string, url_for
from exchange_token import register_athlete
from process_data import gen_report, LEADERBOARD_CSV, DAILY_KM_CSV, INVALID_ACTIVITIES_CSV
import io
import zipfile
from flask import send_file, abort
app = Flask(__name__)

# Simple password for protecting the `/reports` endpoint.
# Set via environment variable `REPORTS_PASSWORD`. Default is 'changeme'.
REPORTS_PASSWORD = "khongcanpass"


def _check_reports_password():
    """Abort with 401 if the incoming request doesn't provide the correct password.

    Accepts the password via (in order):
    - query parameter `password`
    - header `X-Reports-Password`
    - header `Authorization: Bearer <password>`
    """
    expected = REPORTS_PASSWORD
    supplied = (
        request.args.get('password')
        or request.form.get('password')
        or request.headers.get('X-Reports-Password')
    )
    auth = request.headers.get('Authorization')
    if not supplied and auth:
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            supplied = parts[1]
    if supplied != expected:
        return abort(401, description="Unauthorized: invalid password")


def render_reports_form(error=None):
        """Return a Bootstrap-styled HTML form for entering the reports password.

        `error` will be shown as a Bootstrap alert when provided.
        """
        tpl = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <title>Reports - Password</title>
            <style>
                body { background: url('{{ url_for('static', filename='background.png') }}') no-repeat center center fixed; background-size: cover; }
                .overlay { background: rgba(255,255,255,0.9); }
            </style>
        </head>
        <body>
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <div class="card overlay shadow-sm">
                            <div class="card-body">
                                <h3 class="card-title mb-3">Download Reports</h3>
                                <p class="text-muted">Enter the password to generate and download the reports zip.</p>
                                {% if error %}
                                <div class="alert alert-danger" role="alert">{{ error }}</div>
                                {% endif %}
                                <form method="post" action="/reports">
                                    <div class="mb-3">
                                        <label for="password" class="form-label">Password</label>
                                        <input type="password" class="form-control" id="password" name="password" required autofocus>
                                    </div>
                                    <div class="d-grid">
                                        <button class="btn btn-primary" type="submit">Get reports</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return render_template_string(tpl, error=error)

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
                                                tpl = """
                                                <!doctype html>
                                                <html>
                                                <head>
                                                    <meta charset="utf-8" />
                                                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                                                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
                                                    <title>Registered</title>
                                                    <style>
                                                        body { background: url('{{ url_for('static', filename='background.png') }}') no-repeat center center fixed; background-size: cover; }
                                                        .overlay { background: rgba(255,255,255,0.85); }
                                                    </style>
                                                </head>
                                                <body>
                                                    <div class="container py-5">
                                                        <div class="row justify-content-center">
                                                            <div class="col-md-8">
                                                                <div class="card overlay shadow-sm">
                                                                    <div class="card-body">
                                                                        <h1 class="card-title">Success!</h1>
                                                                        <p class="lead">Thanks {{ firstname }} {{ lastname }} for registering.</p>
                                                                        <a href="/" class="btn btn-outline-secondary">Back</a>
                                                                        <a href="/reports" class="btn btn-primary ms-2">Download reports</a>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </body>
                                                </html>
                                                """
                                                return render_template_string(tpl, firstname=athlete_info.get('firstname'), lastname=athlete_info.get('lastname'))
                except Exception as e:
                        return f"<h1>Error!</h1><p>Failed to register athlete: {str(e)}</p>"

        scope = "read,activity:read_all"
        auth_url = (
                f"https://www.strava.com/oauth/authorize?"
                f"client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={scope}"
        )

        tpl = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <title>Larion Strava OAuth</title>
            <style>
                body { background: url('{{ url_for('static', filename='background.png') }}') no-repeat center center fixed; background-size: cover; }
                .overlay { background: rgba(255,255,255,0.9); }
            </style>
        </head>
        <body>
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <div class="card overlay shadow-sm">
                            <div class="card-body text-center">
                                <h1 class="mb-3">Larion Strava OAuth</h1>
                                <p class="mb-4">Authorize the app with Strava to allow data access.</p>
                                <a href="{{ auth_url }}" class="btn btn-success btn-lg">Authorize on Strava</a>
                                <a href="/reports" class="btn btn-primary btn-lg ms-2">Download reports</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return render_template_string(tpl, auth_url=auth_url)

@app.route('/reports', methods=['GET', 'POST'])
def reports():
    # Determine if request includes any non-form auth (query/header).
    has_query_pw = bool(request.args.get('password'))
    has_header_pw = bool(request.headers.get('X-Reports-Password') or request.headers.get('Authorization'))

    # If GET and no header/query auth, show the Bootstrap form
    if request.method == 'GET' and not (has_query_pw or has_header_pw):
        return render_reports_form()

    # If POST, validate the posted form password and show friendly error
    if request.method == 'POST':
        form_pw = request.form.get('password')
        if not form_pw:
            return render_reports_form(error='Please provide a password')
        if form_pw != REPORTS_PASSWORD:
            return render_reports_form(error='Invalid password')

        # form password ok -> generate the report
        gen_report()

    else:
        # Non-POST path where header/query password was supplied: use existing check
        pw_check = _check_reports_password()
        if pw_check is not None:
            return pw_check
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
