import plotly.express as px
from pandas import DataFrame as df
from canvasapi import Canvas
from flask import Flask, request, session, render_template, redirect, url_for
from plotly.io import to_html

app = Flask(__name__)
app.config.update(
    TESTING=True,
    SECRET_KEY=b'kdjshfdfc 7868743rc3$@#%@#$FG@#VRt23r4tv43rt34rv'
)

CANVAS_TOKEN_PARAM = 'canvasToken'
CANVAS_URL_PARAM = 'canvasUrl'
CANVAS_NAME_PARAM = 'name'


def get_token_and_institution_url():
    print(request.form)
    return request.form.get(CANVAS_URL_PARAM), request.form.get(CANVAS_TOKEN_PARAM)


def get_canvas():
    return Canvas(session[CANVAS_URL_PARAM], session[CANVAS_TOKEN_PARAM])


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        institution_url, token = get_token_and_institution_url()
        canvas = Canvas(institution_url, token)
        current_user = canvas.get_current_user()
        session[CANVAS_TOKEN_PARAM] = token
        session[CANVAS_URL_PARAM] = institution_url
        session[CANVAS_NAME_PARAM] = current_user.name
    return redirect(url_for('course'))


@app.route('/course')
def course():
    name = session[CANVAS_NAME_PARAM]
    courses = []
    canvas = get_canvas()
    for course in canvas.get_courses():
        if not hasattr(course, 'name'):
            continue
        courses.append(course)
    return render_template('select_course.html', name=name, courses=courses)


@app.route('/course/<course_id>')
def show_grade(course_id):
    canvas = get_canvas()
    course = canvas.get_course(course_id)
    current_user = canvas.get_current_user()
    submission_data = []
    groups = {}
    for group in course.get_assignment_groups():
        groups[group.id] = (group, [])
    for assignment in course.get_assignments():
        if not hasattr(assignment, 'has_submitted_submissions'):
            continue
        if hasattr(assignment, 'omit_from_final_grade') and assignment.omit_from_final_grade:
            continue
        # points_possible = assignment.points_possible
        # score = None
        submission = None
        if assignment.has_submitted_submissions:
            submission = assignment.get_submission(user=current_user)
            # score = submission.score
        groups[assignment.assignment_group_id][1].append((assignment, submission))

    for group, assignments_and_submissions in groups.values():
        if group.group_weight and group.group_weight > 0:
            for assignment, submission in assignments_and_submissions:
                submission_score = "N/A"
                submission_graded_at_date = "ungraded"
                assignment_points_possible = "N/A"
                if submission:
                    if getattr(submission, 'score', None) is not None:
                        submission_score = submission.score
                    if getattr(submission, 'graded_at_date', None) is not None:
                        submission_graded_at_date = submission.graded_at_date
                if assignment:
                    if getattr(assignment, 'points_possible', None) is not None:
                        assignment_points_possible = assignment.points_possible
                submission_data.append([str(x) for x in [group, group.group_weight, assignment, submission_score, assignment_points_possible, submission_graded_at_date]])
    submission_data = df(submission_data, columns=["group", "group_weight", "assignment", "submission_score", "assignment_points_possible", 'submission_graded_at_date'])
    submission_data['count'] = submission_data.groupby('group')['group'].transform('count')
    fig = px.bar(submission_data, x='group', y='assignment')
    html = to_html(fig).split("<body>", 1)[-1].split("</body>", 1)[0]
    return render_template('course.html', name=session[CANVAS_NAME_PARAM], course=course, html=html)


if __name__ == '__main__':
    app.run()
