import plotly.graph_objects as go
from canvasapi import Canvas
from flask import Flask, request, session, render_template, redirect, url_for
from pandas import DataFrame as df
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
    for course in reversed(list(canvas.get_courses())):
        if not hasattr(course, 'name'):
            continue
        course.name = course.name.replace('-', ' ')
        course.name = course.name.strip()
        courses.append(course)
    return render_template('select_course.html', name=name, courses=courses)


@app.route('/course/<course_id>')
def show_grade(course_id):
    course, submission_data = get_course_and_submission_data(course_id)
    html = create_graph(submission_data)
    return render_template('course.html', name=session[CANVAS_NAME_PARAM], course=course, html=html)


def get_course_and_submission_data(course_id):
    canvas = get_canvas()
    course = canvas.get_course(course_id)
    groups = get_group_data(canvas, course)
    submission_data = get_submission_data(groups)
    return course, submission_data


def get_group_data(canvas, course):
    current_user = canvas.get_current_user()
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
    return groups


def get_submission_data(groups):
    submission_data = []
    for group, assignments_and_submissions in groups.values():
        if group.group_weight and group.group_weight > 0:
            for assignment, submission in assignments_and_submissions:
                submission_score = "N/A"
                submission_graded_at_date = None
                assignment_points_possible = None
                if submission:
                    if submission.workflow_state != 'graded':
                        continue
                    if getattr(submission, 'score', None) is not None:
                        submission_score = submission.score
                    if getattr(submission, 'graded_at_date', None) is not None:
                        submission_graded_at_date = submission.graded_at_date

                if assignment:
                    if getattr(assignment, 'points_possible', None) is not None:
                        assignment_points_possible = assignment.points_possible
                submission_data.append([str(x) for x in [group, group.group_weight, assignment, submission_score,
                                                         assignment_points_possible, submission_graded_at_date]])
    return submission_data


def calculate_score_from_group_grades(group_grades):
    total_weighted_score = 0
    total_weight = 0
    for possible, current, weight in group_grades.values():
        if possible == 0:
            continue
        score = current / possible
        weighted_score = score * weight
        total_weighted_score += weighted_score
        total_weight += weight
    print(group_grades)
    return total_weighted_score / total_weight


def create_graph(submission_data):
    submission_data = df(submission_data, columns=["group", "group_weight", "assignment", "submission_score",
                                                   "assignment_points_possible", 'submission_graded_at_date'])

    # Remove submissions where there's no submission_graded_at_date
    submission_data = submission_data[submission_data.submission_graded_at_date != 'None']

    # Sort submissions by when they were graded
    submission_data = submission_data.sort_values(by='submission_graded_at_date')

    # None represents no assignments being graded yet
    group_grades = {group: [0, 0, 0] for group in submission_data.group.unique()}

    grades_with_dates = []

    for index, row in submission_data.iterrows():
        possible, current, weight = group_grades[row.group]
        weight = float(row.group_weight) / 100
        current += float(row.submission_score)
        possible += float(row.assignment_points_possible)
        group_grades[row.group] = [possible, current, weight]
        current_score = calculate_score_from_group_grades(group_grades)
        grades_with_dates.append((row.submission_graded_at_date, current_score))

    grades_with_dates = df(grades_with_dates, columns=['submission_graded_at_date', 'current_score'])

    #
    # submission_data['count'] = submission_data.groupby('group')['group'].transform('count')
    # fig = px.bar(submission_data, x='group', y='assignment')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grades_with_dates['submission_graded_at_date'], y=grades_with_dates['current_score'],
                             name='Grade'))

    for num, color, name in reversed(
            [*zip([0.6, 0.7, 0.8, 0.9], ['Red', 'Orange', 'Yellow', 'Green'], ['D', 'C', 'B', 'A'])]):
        fig.add_trace(
            go.Scatter(x=grades_with_dates['submission_graded_at_date'], y=[num] * len(grades_with_dates), name=name))

    print(grades_with_dates)

    html = to_html(fig).split("<body>", 1)[-1].split("</body>", 1)[0]
    return html


if __name__ == '__main__':
    app.run()
