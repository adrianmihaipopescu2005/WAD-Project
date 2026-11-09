from flask_wtf import FlaskForm
from wtforms import DateField, EmailField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp

from ..admin.forms import EMAIL_PATTERN


def _optional_int(value):
    """An empty or tampered choice becomes None, so DataRequired shows the friendly message."""
    return int(value) if str(value).isdigit() else None


class PublicAbsenceForm(FlaskForm):
    # The template renders the choices grouped by team; the service checks the student exists.
    student_id = SelectField(
        "Your name", coerce=_optional_int, validate_choice=False,
        validators=[DataRequired(message="Choose your team and your name.")],
    )
    start_date = DateField(
        "Session you'll miss",
        validators=[DataRequired(message="Pick a date.")],
        description="On your team's lab day. Report it by 23:59 the day before at the latest.",
    )
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(max=500)])
    email = EmailField(
        "Your email",
        validators=[
            DataRequired(message="Enter your email, so you can be told the decision."),
            Length(max=255),
            Regexp(EMAIL_PATTERN, message="Enter a valid email address."),
        ],
        description="You'll get an email when your absence is marked motivated or not.",
    )
    submit = SubmitField("Report absence")
